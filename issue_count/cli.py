"""Command-line entry point."""
import argparse
import os
import sys

from .github import fetch_issues
from .report import render
from .stats import summarize


def build_parser():
    parser = argparse.ArgumentParser(
        prog="issue_count",
        description="Count the issues of a GitHub repository and write an HTML report.",
    )
    parser.add_argument("repo", help="repository as owner/name, e.g. octocat/Hello-World")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"),
                        help="GitHub token (default: $GITHUB_TOKEN); optional for public repos")
    parser.add_argument("--label", help="only count issues with this label")
    parser.add_argument("--out", default="report.html", help="output file (default: report.html)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        issues = fetch_issues(args.repo, args.token, args.label)
    except Exception as error:
        sys.exit(f"Error: could not fetch issues for {args.repo}: {error}")

    summary = summarize(issues)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(args.repo, summary))
    print(f"{args.repo}: {summary['total']} issues "
          f"({summary['open']} open, {summary['closed']} closed)")
    if summary["avg_days_to_close"] is not None:
        print(f"Average time to close: {summary['avg_days_to_close']} days")
    print(f"Report written to {args.out}")
