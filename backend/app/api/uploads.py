from __future__ import annotations

import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile

from ..core.config import settings
from ..services.storage import LocalArtifactStorage
from ..schemas.uploads import UploadImageResponse, UploadResponse
from .auth import get_current_user


router = APIRouter(prefix="/uploads", tags=["uploads"])
storage = LocalArtifactStorage(settings.storage_root)


@router.post("/tracks", response_model=UploadResponse)
async def upload_tracks(
    files: List[UploadFile] = File(...),
    user=Depends(get_current_user),
) -> UploadResponse:
    upload_id = str(uuid.uuid4())
    up_dir = storage.upload_tracks_dir(user.user_id, upload_id)
    up_dir.mkdir(parents=True, exist_ok=True)

    saved: List[str] = []
    for f in files:
        name = storage.safe_filename(f.filename or "track")
        dest = up_dir / name
        data = await f.read()
        dest.write_bytes(data)
        saved.append(name)

    return UploadResponse(upload_id=upload_id, files=saved)


@router.post("/image", response_model=UploadImageResponse)
async def upload_image(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
) -> UploadImageResponse:
    upload_id = str(uuid.uuid4())
    up_dir = storage.upload_images_dir(user.user_id, upload_id)
    up_dir.mkdir(parents=True, exist_ok=True)

    name = storage.safe_filename(file.filename or "image")
    dest = up_dir / name
    data = await file.read()
    dest.write_bytes(data)

    return UploadImageResponse(upload_id=upload_id, filename=name)


