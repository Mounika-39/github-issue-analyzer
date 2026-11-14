"""IssueCount API and website."""
import asyncio
import re
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .github_client import GitHubClient, GitHubError
from .service import get_history, get_summary

NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="IssueCount API",
    version="1.0.0",
    description="Issue counts, health score and trends for any public GitHub repository. "
                "Results are cached so GitHub's rate limit is rarely a problem.",
)


@app.exception_handler(GitHubError)
async def github_error_handler(request, exc):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


async def get_github(settings: Settings = Depends(get_settings)):
    client = GitHubClient(settings.github_token)
    try:
        yield client
    finally:
        await client.aclose()


def valid_repo(owner, repo):
    """Only accept plain GitHub names, so nothing odd is ever put into a GitHub URL."""
    for part in (owner, repo):
        if not NAME.match(part) or not part.strip("."):
            raise HTTPException(status_code=400, detail="Invalid repository name.")
    return f"{owner}/{repo}"


def split_repo(value):
    parts = value.strip().split("/")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Use the form owner/repo.")
    return valid_repo(*parts)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/api/repos/{owner}/{repo}/summary", tags=["issues"])
async def summary(owner: str, repo: str,
                  label: Optional[str] = Query(None, max_length=100),
                  settings: Settings = Depends(get_settings),
                  github: GitHubClient = Depends(get_github)):
    """Counts, per-month numbers, top labels and assignees, and the health score."""
    return await get_summary(valid_repo(owner, repo), label, settings, github)


@app.get("/api/repos/{owner}/{repo}/history", tags=["issues"])
def history(owner: str, repo: str,
            label: Optional[str] = Query(None, max_length=100),
            settings: Settings = Depends(get_settings)):
    """One saved snapshot per day, for trend charts."""
    name = valid_repo(owner, repo)
    return {"repo": name, "label": label or "", "points": get_history(name, label, settings)}


@app.get("/api/compare", tags=["issues"])
async def compare(a: str, b: str,
                  label: Optional[str] = Query(None, max_length=100),
                  settings: Settings = Depends(get_settings),
                  github: GitHubClient = Depends(get_github)):
    """The summaries of two repositories, fetched at the same time."""
    repo_a, repo_b = split_repo(a), split_repo(b)
    results = await asyncio.gather(
        get_summary(repo_a, label, settings, github),
        get_summary(repo_b, label, settings, github),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            raise result
    return {"a": results[0], "b": results[1]}


# The website itself. Mounted last so it never hides an /api route.
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
