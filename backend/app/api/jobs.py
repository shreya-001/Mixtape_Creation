from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.config import settings
from ..db.sqlite import SQLiteJobStore
from ..schemas.jobs import ArtifactLinks, CreateJobRequest, JobStatusResponse
from ..services.storage import LocalArtifactStorage
from ..services.jobs import start_job_in_thread
from .auth import get_current_user


router = APIRouter(prefix="/jobs", tags=["jobs"])
storage = LocalArtifactStorage(settings.storage_root)
store = SQLiteJobStore(settings.storage_root / "db" / "jobs.sqlite3")


def _artifact_links(request: Request, user_id: str, job_id: str) -> ArtifactLinks:
    jp = storage.job_paths(user_id, job_id)
    links = ArtifactLinks()

    def url(name: str) -> str:
        return str(request.base_url).rstrip("/") + f"/jobs/{job_id}/artifacts/{name}"

    if (jp.outputs_dir / "mix.mp3").exists():
        links.mix_mp3 = url("mix.mp3")
    if (jp.outputs_dir / "video.mp4").exists():
        links.video_mp4 = url("video.mp4")
    if (jp.outputs_dir / "description.txt").exists():
        links.description_txt = url("description.txt")
    if (jp.outputs_dir / "thumbnail.jpg").exists():
        links.thumbnail = url("thumbnail.jpg")
    return links


@router.post("", response_model=JobStatusResponse)
def create_job(req: CreateJobRequest, request: Request, user=Depends(get_current_user)) -> JobStatusResponse:
    job_id = str(uuid.uuid4())
    jp = storage.job_paths(user.user_id, job_id).ensure()

    meta = req.model_dump()
    meta["job_id"] = job_id
    meta["user_id"] = user.user_id
    store.create_job(job_id, user.user_id, meta)

    # Start processing asynchronously on this machine.
    start_job_in_thread(job_id, store, storage)

    rec = store.get_job(job_id)
    return JobStatusResponse(
        job_id=rec.job_id,
        status=rec.status,
        progress=rec.progress,
        stage=rec.stage,
        error=rec.error,
        artifacts=_artifact_links(request, user.user_id, job_id),
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, request: Request, user=Depends(get_current_user)) -> JobStatusResponse:
    try:
        rec = store.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")

    owner_user_id = rec.owner_user_id()
    if not owner_user_id:
        # Legacy / malformed rows (e.g., pre-migration) must not be accessible cross-user.
        raise HTTPException(status_code=403, detail="Forbidden")
    if owner_user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    meta = json.loads(rec.meta_json)
    youtube_video_id: Optional[str] = meta.get("youtube_video_id")
    youtube_url: Optional[str] = meta.get("youtube_url")

    return JobStatusResponse(
        job_id=rec.job_id,
        status=rec.status,
        progress=rec.progress,
        stage=rec.stage,
        error=rec.error,
        artifacts=_artifact_links(request, owner_user_id, job_id),
        youtube_video_id=youtube_video_id,
        youtube_url=youtube_url,
    )


