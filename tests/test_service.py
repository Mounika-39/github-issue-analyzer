import asyncio

import pytest

from app import db
from app.config import Settings
from app.github_client import GitHubError
from app.service import get_history, get_summary

NOW = 1_760_000_000  # 2025-10-09
DAY = 86400


def issue(n, state, created, closed=None, labels=(), who=()):
    return {
        "number": n, "state": state, "created_at": created, "closed_at": closed,
        "updated_at": closed or created,
        "labels": [{"name": x} for x in labels],
        "assignees": [{"login": x} for x in who],
    }


ISSUES = [
    issue(1, "open", "2025-09-01T10:00:00Z", labels=["bug"], who=["asha"]),
    issue(2, "closed", "2025-09-02T10:00:00Z", "2025-09-04T10:00:00Z", labels=["bug", "docs"]),
]


class FakeGitHub:
    def __init__(self, issues=None, error=None, partial=False):
        self.issues, self.error, self.partial = issues or ISSUES, error, partial
        self.calls = 0

    async def fetch_issues(self, repo, label=None):
        self.calls += 1
        if self.error:
            raise self.error
        return self.issues, self.partial


@pytest.fixture
def settings(tmp_path):
    return Settings(github_token=None, database_path=str(tmp_path / "t.db"), cache_ttl=900)


def run(coro):
    return asyncio.run(coro)


def test_fresh_fetch_returns_counts(settings):
    result = run(get_summary("a/one", None, settings, FakeGitHub(), NOW))
    assert result["summary"]["total"] == 2
    assert (result["cached"], result["stale"], result["partial"]) == (False, False, False)
    assert result["summary"]["avg_days_to_close"] == 2.0
    assert result["health"]["score"] is not None


def test_second_call_inside_ttl_uses_cache(settings):
    github = FakeGitHub()
    run(get_summary("a/one", None, settings, github, NOW))
    again = run(get_summary("a/one", None, settings, github, NOW + 60))
    assert github.calls == 1
    assert again["cached"] is True and again["stale"] is False


def test_cache_key_ignores_repo_case(settings):
    github = FakeGitHub()
    run(get_summary("A/One", None, settings, github, NOW))
    run(get_summary("a/one", None, settings, github, NOW + 1))
    assert github.calls == 1


def test_refetch_after_ttl(settings):
    github = FakeGitHub()
    run(get_summary("a/one", None, settings, github, NOW))
    run(get_summary("a/one", None, settings, github, NOW + settings.cache_ttl + 1))
    assert github.calls == 2


def test_labels_are_cached_separately(settings):
    github = FakeGitHub()
    run(get_summary("a/one", None, settings, github, NOW))
    run(get_summary("a/one", "bug", settings, github, NOW))
    assert github.calls == 2


def test_stale_data_served_when_github_fails(settings):
    run(get_summary("a/one", None, settings, FakeGitHub(), NOW))
    failing = FakeGitHub(error=GitHubError(429, "GitHub rate limit reached."))
    result = run(get_summary("a/one", None, settings, failing, NOW + 10 * DAY))
    assert result["stale"] is True and result["summary"]["total"] == 2


def test_not_found_is_never_masked_by_cache(settings):
    run(get_summary("a/one", None, settings, FakeGitHub(), NOW))
    gone = FakeGitHub(error=GitHubError(404, "Repository not found."))
    with pytest.raises(GitHubError) as caught:
        run(get_summary("a/one", None, settings, gone, NOW + 10 * DAY))
    assert caught.value.status == 404


def test_failure_without_cache_raises(settings):
    failing = FakeGitHub(error=GitHubError(429, "GitHub rate limit reached."))
    with pytest.raises(GitHubError):
        run(get_summary("a/one", None, settings, failing, NOW))


def test_partial_flag_is_kept(settings):
    result = run(get_summary("a/one", None, settings, FakeGitHub(partial=True), NOW))
    assert result["partial"] is True


def test_history_has_one_point_per_day(settings):
    github = FakeGitHub()
    run(get_summary("a/one", None, settings, github, NOW))
    run(get_summary("a/one", None, settings, github, NOW + settings.cache_ttl + 1))  # same day
    assert len(get_history("a/one", None, settings)) == 1

    run(get_summary("a/one", None, settings, github, NOW + DAY))                     # next day
    points = get_history("A/One", None, settings)
    assert len(points) == 2
    assert points[0]["day"] < points[1]["day"]
    assert points[0]["total"] == 2 and points[0]["open"] == 1


def test_history_is_empty_for_unknown_repo(settings):
    assert get_history("x/y", None, settings) == []


def test_database_survives_reopening(settings):
    run(get_summary("a/one", None, settings, FakeGitHub(), NOW))
    assert db.get_cached(settings.database_path, "a/one|")["payload"]["repo"] == "a/one"
