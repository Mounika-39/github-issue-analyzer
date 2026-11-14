"""The core logic: serve from cache when fresh, otherwise fetch from GitHub."""
import json
import time
from datetime import datetime, timezone

from issue_count.stats import summarize

from . import db
from .github_client import GitHubError
from .health import health_metrics


def _iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def get_summary(repo, label, settings, github, now=None):
    """Return the statistics for `repo` (optionally filtered by `label`).

    - A cached result younger than the TTL is returned without calling GitHub.
    - Otherwise GitHub is called and the result is cached and snapshotted.
    - If GitHub fails and an older result exists, that is returned and marked
      stale, so the site keeps working while GitHub is rate limiting us.
      A 404 is never masked this way: the repository really is gone.
    """
    now = time.time() if now is None else now
    label = label or ""
    key = f"{repo.lower()}|{label}"

    cached = db.get_cached(settings.database_path, key)
    if cached and now - cached["fetched_at"] < settings.cache_ttl:
        return {**cached["payload"], "cached": True, "stale": False}

    try:
        issues, partial = await github.fetch_issues(repo, label or None)
    except GitHubError as error:
        if cached and error.status != 404:
            return {**cached["payload"], "cached": True, "stale": True}
        raise

    payload = {
        "repo": repo,
        "label": label,
        "summary": summarize(issues),
        "health": health_metrics(issues, datetime.fromtimestamp(now, timezone.utc)),
        "partial": partial,
        "fetched_at": _iso(now),
    }
    payload = json.loads(json.dumps(payload))  # same shape whether cached or fresh

    db.put_cached(settings.database_path, key, payload, now)
    db.save_snapshot(settings.database_path, repo.lower(), label, _iso(now)[:10],
                     payload["summary"], payload["health"])
    return {**payload, "cached": False, "stale": False}


def get_history(repo, label, settings):
    return db.history(settings.database_path, repo.lower(), label or "")
