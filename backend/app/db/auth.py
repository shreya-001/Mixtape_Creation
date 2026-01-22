from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from ..core.config import settings
from ..core.security import hash_code


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteAuthStore:
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
                CREATE TABLE IF NOT EXISTS users (
                  user_id TEXT PRIMARY KEY,
                  email TEXT UNIQUE NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS login_codes (
                  email TEXT PRIMARY KEY,
                  code_hash TEXT NOT NULL,
                  salt TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oauth_states (
                  state TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS login_oauth_states (
                  state TEXT PRIMARY KEY,
                  expires_at TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS youtube_tokens (
                  user_id TEXT PRIMARY KEY,
                  token_encrypted TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_or_create_user(self, *, user_id: str, email: str) -> str:
        now = _now_iso()
        with self._conn() as conn:
            row = conn.execute("SELECT user_id FROM users WHERE email = ?", (email.lower(),)).fetchone()
            if row is not None:
                return str(row["user_id"])
            conn.execute(
                "INSERT INTO users(user_id, email, created_at) VALUES (?, ?, ?)",
                (user_id, email.lower(), now),
            )
            conn.commit()
            return user_id

    def get_user_by_email(self, email: str) -> Optional[Tuple[str, str]]:
        with self._conn() as conn:
            row = conn.execute("SELECT user_id, email FROM users WHERE email = ?", (email.lower(),)).fetchone()
            if row is None:
                return None
            return str(row["user_id"]), str(row["email"])

    def get_user_by_id(self, user_id: str) -> Optional[Tuple[str, str]]:
        with self._conn() as conn:
            row = conn.execute("SELECT user_id, email FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row is None:
                return None
            return str(row["user_id"]), str(row["email"])

    def upsert_login_code(self, email: str, code: str, salt: str) -> None:
        now = _now_iso()
        expires = (datetime.now(timezone.utc) + timedelta(seconds=settings.login_code_ttl_seconds)).isoformat()
        code_hash = hash_code(email, code, salt)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO login_codes(email, code_hash, salt, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET code_hash=excluded.code_hash, salt=excluded.salt,
                  expires_at=excluded.expires_at, created_at=excluded.created_at
                """,
                (email.lower(), code_hash, salt, expires, now),
            )
            conn.commit()

    def verify_login_code(self, email: str, code: str) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT code_hash, salt, expires_at FROM login_codes WHERE email = ?", (email.lower(),)).fetchone()
            if row is None:
                return False
            expires_at = datetime.fromisoformat(str(row["expires_at"]))
            if expires_at < datetime.now(timezone.utc):
                return False
            salt = str(row["salt"])
            expected = str(row["code_hash"])
            return hash_code(email, code, salt) == expected

    def create_oauth_state(self, state: str, user_id: str, ttl_seconds: int = 600) -> None:
        now = _now_iso()
        expires = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO oauth_states(state, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (state, user_id, expires, now),
            )
            conn.commit()

    def consume_oauth_state(self, state: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute("SELECT user_id, expires_at FROM oauth_states WHERE state = ?", (state,)).fetchone()
            if row is None:
                return None
            expires_at = datetime.fromisoformat(str(row["expires_at"]))
            conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
            conn.commit()
            if expires_at < datetime.now(timezone.utc):
                return None
            return str(row["user_id"])

    def create_login_oauth_state(self, state: str, ttl_seconds: int = 600) -> None:
        now = _now_iso()
        expires = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO login_oauth_states(state, expires_at, created_at) VALUES (?, ?, ?)",
                (state, expires, now),
            )
            conn.commit()

    def consume_login_oauth_state(self, state: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT expires_at FROM login_oauth_states WHERE state = ?",
                (state,),
            ).fetchone()
            if row is None:
                return False
            expires_at = datetime.fromisoformat(str(row["expires_at"]))
            conn.execute("DELETE FROM login_oauth_states WHERE state = ?", (state,))
            conn.commit()
            return expires_at >= datetime.now(timezone.utc)

    def upsert_youtube_token(self, user_id: str, token_encrypted: str) -> None:
        now = _now_iso()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO youtube_tokens(user_id, token_encrypted, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET token_encrypted=excluded.token_encrypted, updated_at=excluded.updated_at
                """,
                (user_id, token_encrypted, now),
            )
            conn.commit()

    def get_youtube_token(self, user_id: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute("SELECT token_encrypted FROM youtube_tokens WHERE user_id = ?", (user_id,)).fetchone()
            if row is None:
                return None
            return str(row["token_encrypted"])


