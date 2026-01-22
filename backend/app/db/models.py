from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    user_id: str | None
    status: str
    created_at: str
    updated_at: str
    error: Optional[str]
    progress: int
    stage: Optional[str]
    meta_json: str

    def owner_user_id(self) -> str | None:
        """Best-effort job owner resolution.

        - Prefer the migrated `user_id` column when present.
        - Fall back to `meta_json["user_id"]` for legacy rows.
        """
        if self.user_id:
            return self.user_id
        try:
            meta = json.loads(self.meta_json or "{}")
        except Exception:
            return None
        uid = meta.get("user_id") if isinstance(meta, dict) else None
        return str(uid) if uid else None


