"""Settings, read from environment variables."""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    github_token: Optional[str]  # kept on the server; users never see it
    database_path: str           # SQLite file for the cache and the history
    cache_ttl: int               # seconds a cached result stays fresh


def get_settings() -> Settings:
    return Settings(
        github_token=os.environ.get("GITHUB_TOKEN") or None,
        database_path=os.environ.get("DATABASE_PATH", "data/issues.db"),
        cache_ttl=int(os.environ.get("CACHE_TTL_SECONDS", "900")),
    )
