"""SQLite storage: a result cache and daily snapshots for trend charts."""
import json
import os
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key        TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    repo     TEXT NOT NULL,
    label    TEXT NOT NULL DEFAULT '',
    day      TEXT NOT NULL,
    total    INTEGER,
    open     INTEGER,
    closed   INTEGER,
    avg_days REAL,
    health   INTEGER,
    UNIQUE (repo, label, day)
);
"""


@contextmanager
def connect(path):
    """Open the database, make sure the tables exist, and commit on exit."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_cached(path, key):
    """Return {"payload", "fetched_at"} for `key`, or None. Age is judged by the caller."""
    with connect(path) as conn:
        row = conn.execute(
            "SELECT payload, fetched_at FROM cache WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    return {"payload": json.loads(row[0]), "fetched_at": row[1]}


def put_cached(path, key, payload, fetched_at):
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO cache (key, payload, fetched_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET payload = excluded.payload, "
            "fetched_at = excluded.fetched_at",
            (key, json.dumps(payload), fetched_at))


def save_snapshot(path, repo, label, day, summary, health):
    """Store one row per repo, label and day. A second fetch the same day overwrites it."""
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO snapshots (repo, label, day, total, open, closed, avg_days, health) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(repo, label, day) DO UPDATE SET total = excluded.total, "
            "open = excluded.open, closed = excluded.closed, "
            "avg_days = excluded.avg_days, health = excluded.health",
            (repo, label, day, summary["total"], summary["open"], summary["closed"],
             summary["avg_days_to_close"], health["score"]))


def history(path, repo, label):
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT day, total, open, closed, avg_days, health FROM snapshots "
            "WHERE repo = ? AND label = ? ORDER BY day", (repo, label)).fetchall()
    keys = ("day", "total", "open", "closed", "avg_days", "health")
    return [dict(zip(keys, row)) for row in rows]
