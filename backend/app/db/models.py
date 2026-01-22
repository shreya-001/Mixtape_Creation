from __future__ import annotations

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


