"""Turning a list of issues into counts."""
from collections import Counter
from datetime import datetime

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def days_to_close(issue):
    """Days between opening and closing an issue, or None if still open."""
    if not issue.get("closed_at"):
        return None
    start = datetime.strptime(issue["created_at"], TIME_FORMAT)
    end = datetime.strptime(issue["closed_at"], TIME_FORMAT)
    return (end - start).total_seconds() / 86400


def summarize(issues, top=10):
    """Return totals, top labels/assignees and per-month opened/closed counts."""
    labels, assignees = Counter(), Counter()
    opened, closed = Counter(), Counter()

    for issue in issues:
        for label in issue.get("labels", []):
            labels[label["name"]] += 1
        for person in issue.get("assignees", []):
            assignees[person["login"]] += 1
        opened[issue["created_at"][:7]] += 1  # "YYYY-MM"
        if issue.get("closed_at"):
            closed[issue["closed_at"][:7]] += 1

    months = sorted(set(opened) | set(closed))
    open_count = sum(1 for i in issues if i["state"] == "open")
    durations = [d for d in map(days_to_close, issues) if d is not None]
    return {
        "avg_days_to_close": round(sum(durations) / len(durations), 1) if durations else None,
        "total": len(issues),
        "open": open_count,
        "closed": len(issues) - open_count,
        "labels": labels.most_common(top),
        "assignees": assignees.most_common(top),
        "months": months,
        "opened": [opened[m] for m in months],
        "closed_per_month": [closed[m] for m in months],
    }
