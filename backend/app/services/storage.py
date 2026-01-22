from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class JobPaths:
    job_dir: Path
    inputs_dir: Path
    outputs_dir: Path
    meta_path: Path
    log_path: Path

    def ensure(self) -> "JobPaths":
        self.inputs_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.job_dir.mkdir(parents=True, exist_ok=True)
        return self


class LocalArtifactStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def job_paths(self, user_id: str, job_id: str) -> JobPaths:
        job_dir = self.root / "users" / user_id / "jobs" / job_id
        return JobPaths(
            job_dir=job_dir,
            inputs_dir=job_dir / "inputs",
            outputs_dir=job_dir / "outputs",
            meta_path=job_dir / "meta.json",
            log_path=job_dir / "logs.txt",
        )

    def upload_tracks_dir(self, user_id: str, upload_id: str) -> Path:
        return self.root / "users" / user_id / "uploads" / upload_id / "tracks"

    def upload_images_dir(self, user_id: str, upload_id: str) -> Path:
        return self.root / "users" / user_id / "uploads" / upload_id / "images"

    def safe_filename(self, name: str) -> str:
        # Very small sanitization to avoid path traversal
        name = os.path.basename(name)
        name = name.replace("..", ".")
        return name


