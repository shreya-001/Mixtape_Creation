from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..core.config import settings
from ..services.storage import LocalArtifactStorage
from ..db.sqlite import SQLiteJobStore
from .auth import get_current_user


router = APIRouter(prefix="/jobs", tags=["artifacts"])
storage = LocalArtifactStorage(settings.storage_root)
store = SQLiteJobStore(settings.storage_root / "db" / "jobs.sqlite3")


@router.get("/{job_id}/artifacts/{name}")
def download_artifact(job_id: str, name: str, user=Depends(get_current_user)):
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

    jp = storage.job_paths(owner_user_id, job_id)
    safe = storage.safe_filename(name)
    path = jp.outputs_dir / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(str(path), filename=safe)


