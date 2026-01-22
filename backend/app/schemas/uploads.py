from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    upload_id: str
    files: List[str]


class UploadImageResponse(BaseModel):
    upload_id: str
    filename: str


