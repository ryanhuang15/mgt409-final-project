"""Single-instance, durable admission ledger and session-scoped review storage."""

import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from contextlib import contextmanager
from pathlib import Path

from dotenv import dotenv_values
from fastapi import HTTPException

from backend.app.config import PROJECT_ROOT


@dataclass(frozen=True)
class WebSettings:
    public: bool = False
    live_enabled: bool = True
    origin: str = ""
    access_code: str = field(default="", repr=False)
    daily_reviews: int = 6
    session_reviews: int = 2
    retention_hours: int = 24
    store_path: Path = PROJECT_ROOT / "runtime/web/lumen.sqlite3"


def web_settings():
    local = PROJECT_ROOT / ".env"
    parent = PROJECT_ROOT.parent / ".env"
    values = dotenv_values(local if local.is_file() else parent, interpolate=False) if local.is_file() or parent.is_file() else {}

    def get(name, default):
        return os.environ.get("WEB_" + name, values.get("WEB_" + name, default))

    public = str(get("PUBLIC_MODE", "false")).lower() == "true"
    config = WebSettings(
        public=public, live_enabled=str(get("LIVE_ENABLED", "false" if public else "true")).lower() == "true",
        origin=str(get("ORIGIN", "")).rstrip("/"), access_code=str(get("ACCESS_CODE", "")),
        daily_reviews=int(get("DAILY_REVIEWS", "6")), session_reviews=int(get("SESSION_REVIEWS", "2")),
        retention_hours=int(get("RETENTION_HOURS", "24")),
        store_path=PROJECT_ROOT / "runtime/web/lumen.sqlite3",
    )
    if not (1 <= config.daily_reviews <= 20 and 1 <= config.session_reviews <= 5 and 1 <= config.retention_hours <= 72):
        raise ValueError("Invalid web limits")
    if public and (not config.origin.startswith("https://") or (config.live_enabled and len(config.access_code) < 16)):
        raise ValueError("Public deployment requires an HTTPS origin and a 16+ character access code for live reviews")
    return config


class ReviewStore:
    def __init__(self, config):
        self.config = config
        config.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, owner TEXT, created REAL, stage TEXT, payload TEXT, result TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS admissions (created REAL, owner TEXT)")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
            if "parent_id" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN parent_id TEXT")
            db.execute("CREATE TABLE IF NOT EXISTS finding_actions (owner TEXT, review_id TEXT, finding_id TEXT, status TEXT, resolution TEXT, updated REAL, PRIMARY KEY(owner,review_id,finding_id))")
            db.execute("CREATE TABLE IF NOT EXISTS finding_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, review_id TEXT, finding_id TEXT, created REAL, status TEXT, note TEXT, resolution TEXT)")
            # A restart never resumes or repeats a paid request automatically.
            db.execute("UPDATE jobs SET stage='interrupted' WHERE stage IN ('validating','rate_analysis','documentation_review')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.config.store_path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def cleanup(self, db):
        now = time.time()
        db.execute("DELETE FROM jobs WHERE created < ?", (now - self.config.retention_hours * 3600,))
        db.execute("DELETE FROM admissions WHERE created < ?", (now - 86400,))
        db.execute("DELETE FROM finding_actions WHERE updated < ?", (now - self.config.retention_hours * 3600,))
        db.execute("DELETE FROM finding_notes WHERE created < ?", (now - self.config.retention_hours * 3600,))

    def prune(self):
        with self.connect() as db:
            self.cleanup(db)

    def admit(self, owner, payload, parent_id=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.cleanup(db)
            if db.execute("SELECT count(*) FROM jobs WHERE stage IN ('validating','rate_analysis','documentation_review')").fetchone()[0]:
                raise HTTPException(429, "Another review is running. Please try again when it finishes.")
            if db.execute("SELECT count(*) FROM admissions").fetchone()[0] >= self.config.daily_reviews:
                raise HTTPException(429, "The shared 24-hour AI review allowance is used. Saved examples remain available.")
            if db.execute("SELECT count(*) FROM admissions WHERE owner=?", (owner,)).fetchone()[0] >= self.config.session_reviews:
                raise HTTPException(429, "This browser's 24-hour AI review allowance is used. Saved examples remain available.")
            job_id = secrets.token_hex(16)
            now = time.time()
            db.execute("INSERT INTO admissions VALUES (?,?)", (now, owner))
            db.execute("INSERT INTO jobs (id,owner,created,stage,payload,result,parent_id) VALUES (?,?,?,?,?,NULL,?)", (job_id, owner, now, "validating", json.dumps(payload), parent_id))
        return job_id

    def update(self, job_id, stage, result=None):
        with self.connect() as db:
            db.execute("UPDATE jobs SET stage=?, result=COALESCE(?,result) WHERE id=?", (stage, json.dumps(result) if result else None, job_id))

    def get(self, job_id, owner):
        with self.connect() as db:
            self.cleanup(db)
            row = db.execute("SELECT * FROM jobs WHERE id=? AND owner=?", (job_id, owner)).fetchone()
        if not row:
            raise HTTPException(404, "Review not found in this browser session, or its retention period has expired.")
        return dict(job_id=row["id"], parent_id=row["parent_id"], stage=row["stage"], source="live", filing=json.loads(row["payload"]),
                    result=json.loads(row["result"]) if row["result"] else None)

    def history(self, owner):
        with self.connect() as db:
            self.cleanup(db)
            rows = db.execute("SELECT id,created,stage,payload,parent_id FROM jobs WHERE owner=? ORDER BY created DESC", (owner,)).fetchall()
        return [dict(job_id=r["id"], parent_id=r["parent_id"], created=r["created"], stage=r["stage"], insurer=json.loads(r["payload"])["metadata"]["insurer"]) for r in rows]

    def actions(self, owner, review_id):
        with self.connect() as db:
            self.cleanup(db)
            current = db.execute("SELECT finding_id,status,resolution,updated FROM finding_actions WHERE owner=? AND review_id=?", (owner, review_id)).fetchall()
            history = db.execute("SELECT finding_id,created,status,note,resolution FROM finding_notes WHERE owner=? AND review_id=? ORDER BY id", (owner, review_id)).fetchall()
        return {"current": {row["finding_id"]: dict(status=row["status"], resolution=row["resolution"], updated_at=row["updated"]) for row in current},
                "history": [dict(row) for row in history]}

    def save_action(self, owner, review_id, finding_id, status, note, resolution):
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.cleanup(db)
            db.execute("INSERT INTO finding_notes (owner,review_id,finding_id,created,status,note,resolution) VALUES (?,?,?,?,?,?,?)",
                       (owner, review_id, finding_id, now, status, note, resolution))
            db.execute("INSERT INTO finding_actions VALUES (?,?,?,?,?,?) ON CONFLICT(owner,review_id,finding_id) DO UPDATE SET status=excluded.status,resolution=excluded.resolution,updated=excluded.updated",
                       (owner, review_id, finding_id, status, resolution, now))
        return self.actions(owner, review_id)
