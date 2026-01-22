from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .models import JobRecord


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteJobStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                  job_id TEXT PRIMARY KEY,
                  user_id TEXT,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  error TEXT,
                  progress INTEGER NOT NULL DEFAULT 0,
                  stage TEXT,
                  meta_json TEXT NOT NULL
                )
                """
            )
            # Migration for existing DBs without user_id
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()]
            if "user_id" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN user_id TEXT")
            conn.commit()

    def create_job(self, job_id: str, user_id: str, meta: Dict[str, Any]) -> JobRecord:
        now = _now_iso()
        meta_json = json.dumps(meta, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO jobs(job_id, user_id, status, created_at, updated_at, error, progress, stage, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, user_id, "queued", now, now, None, 0, "queued", meta_json),
            )
            conn.commit()
        return self.get_job(job_id)

    def update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        error: Optional[str] = None,
        progress: Optional[int] = None,
        stage: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> JobRecord:
        now = _now_iso()
        updates = ["updated_at = ?"]
        values: list[Any] = [now]

        if status is not None:
            updates.append("status = ?")
            values.append(status)
        if error is not None:
            updates.append("error = ?")
            values.append(error)
        if progress is not None:
            updates.append("progress = ?")
            values.append(int(progress))
        if stage is not None:
            updates.append("stage = ?")
            values.append(stage)
        if meta is not None:
            updates.append("meta_json = ?")
            values.append(json.dumps(meta, ensure_ascii=False))

        values.append(job_id)
        with self._conn() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?", values)
            conn.commit()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> JobRecord:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(f"Job not found: {job_id}")
            return JobRecord(**dict(row))  # type: ignore[arg-type]


