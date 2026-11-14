"""Async client for the GitHub REST API."""
import httpx

API = "https://api.github.com"
PER_PAGE = 100
MAX_PAGES = 100  # GitHub stops serving results after 10,000 items


class GitHubError(Exception):
    """An error to show the user. `status` is the HTTP status our API should answer with."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class GitHubClient:
    def __init__(self, token=None, transport=None, base_url=API):
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "issuecount",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=20.0, transport=transport)

    async def aclose(self):
        await self._http.aclose()

    async def fetch_issues(self, repo, label=None):
        """Return (issues, partial). Pull requests are removed.

        `partial` is True when GitHub stopped paging before the end of a very large list.
        """
        issues = []
        for page in range(1, MAX_PAGES + 1):
            params = {"state": "all", "per_page": PER_PAGE, "page": page}
            if label:
                params["labels"] = label
            try:
                res = await self._http.get(f"/repos/{repo}/issues", params=params)
            except httpx.HTTPError:
                raise GitHubError(502, "Could not reach GitHub.")

            if res.status_code == 422 and issues:  # too deep to page any further
                return issues, True
            self._check(res)

            batch = res.json()
            # The issues endpoint also returns pull requests; they carry this key.
            issues.extend(i for i in batch if "pull_request" not in i)
            if len(batch) < PER_PAGE:
                break
        else:
            return issues, True  # hit our own page cap
        return issues, False

    @staticmethod
    def _check(res):
        status = res.status_code
        if status == 200:
            return
        if status == 404:
            raise GitHubError(404, "Repository not found. It may be private or misspelled.")
        if status == 401:
            raise GitHubError(502, "The server's GitHub token was rejected.")
        rate_limited = status == 429 or (
            status == 403 and (res.headers.get("x-ratelimit-remaining") == "0"
                               or "rate limit" in res.text.lower()))
        if rate_limited:
            raise GitHubError(429, "GitHub rate limit reached. Try again later.")
        if status == 403:
            raise GitHubError(403, "GitHub denied access to this repository.")
        raise GitHubError(502, f"GitHub returned an unexpected response ({status}).")
