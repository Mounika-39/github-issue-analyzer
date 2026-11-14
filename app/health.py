"""A simple, explainable health score for a repository's issues.

score = 100 * (0.4 * (1 - stale share of open issues)
             + 0.2 * (1 - unassigned share of open issues)
             + 0.4 * (closed share of all issues))

An open issue is "stale" when nothing has happened on it for STALE_DAYS days.
This is a heuristic for comparing repos at a glance, not a scientific measure.
"""
from datetime import datetime, timezone

STALE_DAYS = 90
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _parse(timestamp):
    return datetime.strptime(timestamp, TIME_FORMAT).replace(tzinfo=timezone.utc)


def health_metrics(issues, now=None):
    now = now or datetime.now(timezone.utc)
    open_issues = [i for i in issues if i["state"] == "open"]

    stale = sum(
        1 for i in open_issues
        if (now - _parse(i.get("updated_at") or i["created_at"])).days >= STALE_DAYS)
    unassigned = sum(1 for i in open_issues if not i.get("assignees"))

    total = len(issues)
    score = None
    if total:
        closed_share = (total - len(open_issues)) / total
        stale_share = stale / len(open_issues) if open_issues else 0
        unassigned_share = unassigned / len(open_issues) if open_issues else 0
        score = round(100 * (0.4 * (1 - stale_share)
                             + 0.2 * (1 - unassigned_share)
                             + 0.4 * closed_share))

    return {
        "score": score,
        "stale_open": stale,
        "unassigned_open": unassigned,
        "stale_days": STALE_DAYS,
    }
