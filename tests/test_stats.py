import unittest

from issue_count.report import render
from issue_count.stats import summarize

ISSUES = [
    {"state": "open", "created_at": "2026-01-05T10:00:00Z", "closed_at": None,
     "labels": [{"name": "bug"}], "assignees": [{"login": "asha"}]},
    {"state": "closed", "created_at": "2026-01-20T10:00:00Z", "closed_at": "2026-02-02T10:00:00Z",
     "labels": [{"name": "bug"}, {"name": "docs"}], "assignees": []},
    {"state": "closed", "created_at": "2026-02-10T10:00:00Z", "closed_at": "2026-02-11T10:00:00Z",
     "labels": [], "assignees": [{"login": "asha"}]},
]


class SummarizeTests(unittest.TestCase):
    def test_totals(self):
        s = summarize(ISSUES)
        self.assertEqual((s["total"], s["open"], s["closed"]), (3, 1, 2))

    def test_labels_and_assignees(self):
        s = summarize(ISSUES)
        self.assertEqual(s["labels"][0], ("bug", 2))
        self.assertEqual(s["assignees"], [("asha", 2)])

    def test_monthly_counts(self):
        s = summarize(ISSUES)
        self.assertEqual(s["months"], ["2026-01", "2026-02"])
        self.assertEqual(s["opened"], [2, 1])
        self.assertEqual(s["closed_per_month"], [0, 2])

    def test_average_days_to_close(self):
        # 13 days and 1 day -> average 7.0
        self.assertEqual(summarize(ISSUES)["avg_days_to_close"], 7.0)

    def test_no_closed_issues_gives_none(self):
        self.assertIsNone(summarize(ISSUES[:1])["avg_days_to_close"])

    def test_empty(self):
        s = summarize([])
        self.assertEqual((s["total"], s["months"]), (0, []))


class RenderTests(unittest.TestCase):
    def test_report_contains_repo_and_counts(self):
        page = render("octo/<repo>", summarize(ISSUES))
        self.assertIn("octo/&lt;repo&gt;", page)
        self.assertIn("<b>3</b>Total", page)


if __name__ == "__main__":
    unittest.main()
