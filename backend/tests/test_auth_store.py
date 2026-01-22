from __future__ import annotations

import threading
import tempfile
from pathlib import Path

import unittest

from backend.app.db.auth import SQLiteAuthStore


class TestSQLiteAuthStoreVerifyLoginCode(unittest.TestCase):
    def test_verify_login_code_is_one_time_use_under_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "auth.sqlite3"
            store = SQLiteAuthStore(db_path)

            email = "test@example.com"
            code = "123456"
            salt = "deadbeef"
            store.upsert_login_code(email, code, salt)

            barrier = threading.Barrier(2)
            lock = threading.Lock()
            results: list[bool] = []

            def worker() -> None:
                barrier.wait()
                ok = store.verify_login_code(email, code)
                with lock:
                    results.append(ok)

            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start()
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)

            self.assertEqual(len(results), 2, f"Expected 2 results, got {results!r}")
            self.assertEqual(results.count(True), 1, f"Expected exactly one success, got {results!r}")
            self.assertEqual(results.count(False), 1, f"Expected exactly one failure, got {results!r}")

            # Subsequent attempts must fail (row already consumed).
            self.assertFalse(store.verify_login_code(email, code))


