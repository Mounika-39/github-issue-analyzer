"""Fetching issues from the GitHub REST API."""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
PER_PAGE = 100
MAX_PAGES = 100  # the API stops serving results after 10,000 items


def fetch_issues(repo, token=None, label=None):
    """Return every issue (open and closed) of `repo`, excluding pull requests.

    `repo` is "owner/name". `token` is optional for public repositories.
    `label`, if given, keeps only issues that carry that label.
    """
    issues = []
    extra = f"&labels={urllib.parse.quote(label)}" if label else ""
    for page in range(1, MAX_PAGES + 1):
        url = (f"{API}/repos/{repo}/issues?state=all&per_page={PER_PAGE}"
               f"&page={page}{extra}")
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "issue-count",
        })
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request) as response:
                batch = json.load(response)
        except urllib.error.HTTPError as error:
            # GitHub answers 422 when a list is too large to page any deeper.
            if error.code == 422 and issues:
                print("Warning: GitHub stopped paging; counts are partial.",
                      file=sys.stderr)
                break
            raise
        # The issues endpoint also returns pull requests; they carry this key.
        issues.extend(i for i in batch if "pull_request" not in i)
        if len(batch) < PER_PAGE:
            break
    return issues
