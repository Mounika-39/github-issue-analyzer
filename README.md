# GitHub Issue Analyzer

Paste a GitHub repository and get its issue counts, a health score and charts.
You can also compare two repositories side by side.

## Features

- Total, open and closed issues (pull requests are not counted)
- Average days to close an issue
- Health score from 0 to 100
- Issues opened and closed per month, top labels, top assignees
- Trend over time: one snapshot is saved per day, so the chart grows as you use it
- Compare two repositories
- Label filter, CSV download, print to PDF, dark mode

## Tech

- Python and FastAPI for the API
- SQLite for the cache and the saved history
- HTML, CSS and JavaScript with Chart.js for the website
- pytest for tests, Docker for packaging, GitHub Actions for CI

## How it works

The website asks the server for a repository. The server asks GitHub, saves the answer
for 15 minutes, and sends it back. If GitHub refuses a request and an older saved answer
exists, the older answer is shown and marked as saved data.

## Run it

With Docker:

```
docker compose up --build
```

Without Docker:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://localhost:8000. The API documentation is at http://localhost:8000/docs.

## Tests

```
pip install -r requirements-dev.txt
python -m pytest
```

## API

| Endpoint | Returns |
|---|---|
| `GET /api/repos/{owner}/{repo}/summary?label=` | Counts, monthly numbers, top labels and assignees, health score |
| `GET /api/repos/{owner}/{repo}/history?label=` | Saved daily snapshots |
| `GET /api/compare?a=owner/repo&b=owner/repo` | Summaries of two repositories |
| `GET /api/health` | `{"status": "ok"}` |

## Settings

Copy `.env.example` to `.env` to change these. All are optional.

| Variable | Default | Meaning |
|---|---|---|
| `GITHUB_TOKEN` | none | GitHub token, raises the rate limit from 60 to 5,000 requests per hour |
| `CACHE_TTL_SECONDS` | `900` | How long a result is reused before asking GitHub again |
| `DATABASE_PATH` | `data/issues.db` | Where the SQLite file is stored |

## Project layout

```
app/          the API (routes, GitHub client, cache, health score)
static/       the website
tests/        automatic tests
issue_count/  a small command-line version
```

Command-line version:

```
python -m issue_count owner/repo
```
