import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.github_client import GitHubClient
from app.main import app, get_github


def issue(n, state="open", created="2026-01-05T10:00:00Z", closed=None, **extra):
    return {"number": n, "state": state, "created_at": created, "closed_at": closed,
            "updated_at": closed or created, "labels": [{"name": "bug"}],
            "assignees": [], **extra}


ISSUES = [
    issue(1),
    issue(2, "closed", "2026-01-20T10:00:00Z", "2026-02-02T10:00:00Z"),
    issue(3, "closed", "2026-02-10T10:00:00Z", "2026-02-11T10:00:00Z"),
    issue(4, pull_request={"url": "x"}),  # pull requests must not be counted
]


class Fake:
    """Stands in for GitHub. Set `handler` to change what GitHub answers."""

    def __init__(self):
        self.calls = 0
        self.handler = self.ok

    def ok(self, request):
        page = int(request.url.params["page"])
        return httpx.Response(200, json=ISSUES if page == 1 else [])

    def __call__(self, request):
        self.calls += 1
        return self.handler(request)


@pytest.fixture
def api(tmp_path):
    fake = Fake()
    settings = Settings(github_token=None, database_path=str(tmp_path / "t.db"), cache_ttl=900)

    async def github():
        client = GitHubClient(None, transport=httpx.MockTransport(fake))
        try:
            yield client
        finally:
            await client.aclose()

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_github] = github
    with TestClient(app) as client:
        yield client, fake, settings
    app.dependency_overrides.clear()


def test_health_endpoint(api):
    client, _, _ = api
    assert client.get("/api/health").json() == {"status": "ok"}


def test_summary_counts_and_excludes_pull_requests(api):
    client, _, _ = api
    body = client.get("/api/repos/a/one/summary").json()
    assert body["summary"]["total"] == 3
    assert (body["summary"]["open"], body["summary"]["closed"]) == (1, 2)
    assert body["summary"]["avg_days_to_close"] == 7.0
    assert body["cached"] is False and body["partial"] is False
    assert body["health"]["score"] is not None


def test_second_request_comes_from_cache(api):
    client, fake, _ = api
    client.get("/api/repos/a/one/summary")
    body = client.get("/api/repos/a/one/summary").json()
    assert fake.calls == 1 and body["cached"] is True


def test_label_is_sent_to_github(api):
    client, fake, _ = api
    seen = {}

    def handler(request):
        seen["labels"] = request.url.params.get("labels")
        return fake.ok(request)

    fake.handler = handler
    client.get("/api/repos/a/one/summary", params={"label": "bug"})
    assert seen["labels"] == "bug"


def test_unknown_repo_gives_404(api):
    client, fake, _ = api
    fake.handler = lambda r: httpx.Response(404, json={"message": "Not Found"})
    res = client.get("/api/repos/a/missing/summary")
    assert res.status_code == 404 and "not found" in res.json()["detail"].lower()


def test_rate_limit_gives_429(api):
    client, fake, _ = api
    fake.handler = lambda r: httpx.Response(403, headers={"x-ratelimit-remaining": "0"})
    res = client.get("/api/repos/a/one/summary")
    assert res.status_code == 429 and "rate limit" in res.json()["detail"].lower()


def test_forbidden_without_rate_limit_gives_403(api):
    client, fake, _ = api
    fake.handler = lambda r: httpx.Response(403, json={"message": "Repository access blocked"})
    assert client.get("/api/repos/a/one/summary").status_code == 403


def test_unexpected_github_error_gives_502(api):
    client, fake, _ = api
    fake.handler = lambda r: httpx.Response(500)
    assert client.get("/api/repos/a/one/summary").status_code == 502


def test_network_failure_gives_502(api):
    client, fake, _ = api

    def boom(request):
        raise httpx.ConnectError("no network")

    fake.handler = boom
    res = client.get("/api/repos/a/one/summary")
    assert res.status_code == 502 and "reach github" in res.json()["detail"].lower()


def test_stale_cache_is_served_when_github_fails(api):
    client, fake, settings = api
    client.get("/api/repos/a/one/summary")
    settings.cache_ttl = 0  # everything cached is now expired
    fake.handler = lambda r: httpx.Response(403, headers={"x-ratelimit-remaining": "0"})
    res = client.get("/api/repos/a/one/summary")
    assert res.status_code == 200 and res.json()["stale"] is True


def test_partial_results_when_github_stops_paging(api):
    client, fake, _ = api
    page_of_100 = [issue(n) for n in range(100)]

    def handler(request):
        if int(request.url.params["page"]) == 1:
            return httpx.Response(200, json=page_of_100)
        return httpx.Response(422, json={"message": "pagination limit"})

    fake.handler = handler
    body = client.get("/api/repos/big/repo/summary").json()
    assert body["partial"] is True and body["summary"]["total"] == 100


def test_history_grows_after_a_fetch(api):
    client, _, _ = api
    assert client.get("/api/repos/a/one/history").json()["points"] == []
    client.get("/api/repos/a/one/summary")
    points = client.get("/api/repos/a/one/history").json()["points"]
    assert len(points) == 1 and points[0]["total"] == 3


def test_compare_returns_both_repos(api):
    client, _, _ = api
    body = client.get("/api/compare", params={"a": "a/one", "b": "b/two"}).json()
    assert body["a"]["repo"] == "a/one" and body["b"]["repo"] == "b/two"


def test_compare_fails_cleanly_if_one_repo_is_missing(api):
    client, fake, _ = api

    def handler(request):
        if "/missing/" in request.url.path:
            return httpx.Response(404)
        return fake.ok(request)

    fake.handler = handler
    res = client.get("/api/compare", params={"a": "a/one", "b": "x/missing"})
    assert res.status_code == 404


@pytest.mark.parametrize("path", [
    "/api/repos/bad$name/repo/summary",
    "/api/repos/a/bad name/summary",
    "/api/repos/a/../summary",
    "/api/repos/.../repo/summary",
])
def test_invalid_names_are_rejected(api, path):
    client, fake, _ = api
    res = client.get(path)
    assert res.status_code in (400, 404, 422)
    assert fake.calls == 0  # GitHub is never called with a bad name


@pytest.mark.parametrize("a,b", [("nonsense", "a/b"), ("a/b", "a/b/c"), ("a/b", "")])
def test_compare_validates_input(api, a, b):
    client, fake, _ = api
    assert client.get("/api/compare", params={"a": a, "b": b}).status_code == 400
    assert fake.calls == 0
