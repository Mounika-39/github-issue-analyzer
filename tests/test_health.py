from datetime import datetime, timezone

from app.health import health_metrics

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
OLD = "2025-06-01T00:00:00Z"    # well over 90 days before NOW
FRESH = "2025-12-20T00:00:00Z"  # 12 days before NOW


def issue(state, updated, assignees=()):
    return {"state": state, "created_at": OLD, "updated_at": updated,
            "assignees": [{"login": a} for a in assignees]}


def test_mixed_repo_scores_fifty():
    issues = [
        issue("open", OLD),                   # stale and unassigned
        issue("open", FRESH, ["asha"]),       # fresh and assigned
        issue("closed", FRESH),
        issue("closed", FRESH),
    ]
    h = health_metrics(issues, NOW)
    assert (h["stale_open"], h["unassigned_open"]) == (1, 1)
    assert h["score"] == 50  # 100 * (0.4*0.5 + 0.2*0.5 + 0.4*0.5)


def test_all_closed_is_perfect():
    assert health_metrics([issue("closed", OLD)], NOW)["score"] == 100


def test_all_open_stale_and_unassigned_scores_zero():
    assert health_metrics([issue("open", OLD), issue("open", OLD)], NOW)["score"] == 0


def test_no_issues_has_no_score():
    assert health_metrics([], NOW)["score"] is None


def test_missing_updated_at_falls_back_to_created_at():
    legacy = {"state": "open", "created_at": OLD, "assignees": []}
    assert health_metrics([legacy], NOW)["stale_open"] == 1
