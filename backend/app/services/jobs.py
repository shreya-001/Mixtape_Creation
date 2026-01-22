from __future__ import annotations

import json
import random
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import settings
from ..db.sqlite import SQLiteJobStore
from .description import YouTubeDescriptionOptions, generate_youtube_description
from .metadata import TrackInfo, read_tags_and_duration
from .mixing import build_crossfaded_mixtape
from .storage import LocalArtifactStorage
from .timestamps import compute_track_timings, format_timestamp
from ..db.auth import SQLiteAuthStore
from ..core.security import decrypt_text, encrypt_text
from .youtube import upload_video_with_token_json
from .video import VideoRenderOptions, make_video_from_audio


@dataclass(frozen=True)
class RunOutputs:
    mix_mp3: Path
    description_txt: Path
    video_mp4: Optional[Path] = None


def _log(jp_log: Path, msg: str) -> None:
    jp_log.parent.mkdir(parents=True, exist_ok=True)
    with jp_log.open("a", encoding="utf-8") as f:
        f.write(msg.rstrip() + "\n")


def _copy_inputs_to_job(
    tracks_dir: Path,
    image_path: Path,
    jp_inputs: Path,
    shuffle: bool,
) -> tuple[List[Path], Path]:
    jp_inputs.mkdir(parents=True, exist_ok=True)
    tracks_out = jp_inputs / "tracks"
    tracks_out.mkdir(parents=True, exist_ok=True)
    img_out = jp_inputs / "bg"
    img_out.mkdir(parents=True, exist_ok=True)

    track_files = sorted([p for p in tracks_dir.iterdir() if p.is_file()])
    if shuffle:
        random.shuffle(track_files)

    copied_tracks: List[Path] = []
    for p in track_files:
        dest = tracks_out / p.name
        shutil.copy2(p, dest)
        copied_tracks.append(dest)

    dest_img = img_out / image_path.name
    shutil.copy2(image_path, dest_img)

    return copied_tracks, dest_img


def run_job(job_id: str, store: SQLiteJobStore, storage: LocalArtifactStorage) -> RunOutputs:
    rec = store.get_job(job_id)
    meta: Dict[str, Any] = json.loads(rec.meta_json)
    user_id = str(meta.get("user_id") or rec.user_id or "")
    if not user_id:
        raise RuntimeError("Job missing user_id")

    jp = storage.job_paths(user_id, job_id).ensure()

    def update(**kwargs: Any) -> None:
        store.update_job(job_id, **kwargs)

    try:
        update(status="running", stage="ingest", progress=5, error=None)
        _log(jp.log_path, f"[ingest] job_id={job_id}")

        tracks_upload_id = meta["tracks_upload_id"]
        bg_upload_id = meta["bg_image_upload_id"]

        tracks_dir = storage.upload_tracks_dir(user_id, tracks_upload_id)
        images_dir = storage.upload_images_dir(user_id, bg_upload_id)
        if not tracks_dir.exists():
            raise FileNotFoundError(f"Tracks upload not found: {tracks_upload_id}")
        if not images_dir.exists():
            raise FileNotFoundError(f"Image upload not found: {bg_upload_id}")
        image_path = next(iter(sorted(images_dir.iterdir())))

        shuffle = bool(meta.get("shuffle", True))
        transition_ms = int(meta.get("transition_ms", 6000))
        mixtape_title = str(meta.get("mixtape_title", "Smooth Fade EDM Mixtape"))
        make_video = bool(meta.get("make_video", True))

        copied_tracks, copied_image = _copy_inputs_to_job(tracks_dir, image_path, jp.inputs_dir, shuffle=shuffle)
        _log(jp.log_path, f"[ingest] copied_tracks={len(copied_tracks)} image={copied_image.name}")

        # Read tags/durations in this order (this defines the tracklist order)
        tracks: List[TrackInfo] = []
        for p in copied_tracks:
            title, artist, dur_s = read_tags_and_duration(str(p))
            tracks.append(TrackInfo(filename=p.name, title=title, artist=artist, duration_s=dur_s, path=str(p)))

        update(stage="mix", progress=25)
        _log(jp.log_path, "[mix] starting")
        mix_path = jp.outputs_dir / "mix.mp3"
        mix_res = build_crossfaded_mixtape([t.path for t in tracks], str(mix_path), transition_ms=transition_ms)
        _log(jp.log_path, f"[mix] wrote={mix_res.output_path} duration_ms={mix_res.duration_ms}")

        update(stage="describe", progress=45)
        _log(jp.log_path, "[describe] starting")
        desc_opts = YouTubeDescriptionOptions(mixtape_title=mixtape_title, shuffle=shuffle, transition_ms=transition_ms)
        desc = generate_youtube_description(tracks, desc_opts)
        desc_path = jp.outputs_dir / "description.txt"
        desc_path.write_text(desc, encoding="utf-8")

        # Write meta.json (including computed timings)
        timings, total_s = compute_track_timings([t.duration_s for t in tracks], transition_ms=transition_ms)
        meta_out = {
            "job_id": job_id,
            "settings": {
                "mixtape_title": mixtape_title,
                "shuffle": shuffle,
                "transition_ms": transition_ms,
            },
            "tracks": [
                {
                    "index": ti.index,
                    "filename": t.filename,
                    "title": t.title,
                    "artist": t.artist,
                    "duration_s": t.duration_s,
                    "start_s": ti.start_s,
                    "start_ts": format_timestamp(ti.start_s),
                }
                for t, ti in zip(tracks, timings)
            ],
            "total_duration_s": total_s,
            "total_duration_ts": format_timestamp(total_s),
        }
        jp.meta_path.write_text(json.dumps(meta_out, ensure_ascii=False, indent=2), encoding="utf-8")

        video_path: Optional[Path] = None
        if make_video:
            update(stage="render", progress=70)
            _log(jp.log_path, "[render] starting")
            video_path = jp.outputs_dir / "video.mp4"
            make_video_from_audio(
                image_path=str(copied_image),
                audio_path=str(mix_path),
                output_path=str(video_path),
                opts=VideoRenderOptions(),
            )
            _log(jp.log_path, f"[render] wrote={video_path}")

        # Optional: upload to YouTube if configured
        yt = meta.get("youtube")
        if yt and video_path and video_path.exists():
            update(stage="upload", progress=85)
            _log(jp.log_path, "[upload] starting")
            # If user didn't provide description, use generated description.txt
            yt_title = yt.get("title") or mixtape_title
            yt_desc = yt.get("description") or desc
            yt_tags = yt.get("tags") or []
            yt_privacy = yt.get("privacy_status") or "unlisted"

            auth_store = SQLiteAuthStore(settings.storage_root / "db" / "auth.sqlite3")
            token_enc = auth_store.get_youtube_token(user_id)
            if not token_enc:
                raise RuntimeError("User has not connected YouTube yet.")
            token_json = decrypt_text(token_enc)

            def _persist(updated_token_json: str) -> None:
                auth_store.upsert_youtube_token(user_id, encrypt_text(updated_token_json))

            res = upload_video_with_token_json(
                token_json=token_json,
                video_path=video_path,
                title=yt_title,
                description=yt_desc,
                tags=yt_tags,
                privacy_status=yt_privacy,
                thumbnail_path=(jp.outputs_dir / "thumbnail.jpg") if (jp.outputs_dir / "thumbnail.jpg").exists() else None,
                on_token_json_updated=_persist,
            )
            _log(jp.log_path, f"[upload] video_id={res.video_id}")
            meta["youtube_video_id"] = res.video_id
            meta["youtube_url"] = res.url
            update(meta=meta)

        update(stage="done", progress=100, status="done")
        _log(jp.log_path, "[done]")
        return RunOutputs(mix_mp3=mix_path, description_txt=desc_path, video_mp4=video_path)

    except Exception as e:
        _log(jp.log_path, f"[error] {type(e).__name__}: {e}")
        update(status="error", stage="error", progress=100, error=str(e))
        raise


def start_job_in_thread(job_id: str, store: SQLiteJobStore, storage: LocalArtifactStorage) -> None:
    def _target() -> None:
        run_job(job_id, store, storage)

    t = threading.Thread(target=_target, name=f"job-{job_id}", daemon=True)
    t.start()


