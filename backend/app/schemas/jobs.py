from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class YouTubeSettings(BaseModel):
    title: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    privacy_status: str = Field(default="unlisted", pattern="^(private|unlisted|public)$")


class CreateJobRequest(BaseModel):
    mixtape_title: str = "Smooth Fade EDM Mixtape | Seamless Transitions"
    shuffle: bool = True
    transition_ms: int = 6000

    # Upload identifiers (from /uploads endpoints)
    tracks_upload_id: str
    bg_image_upload_id: str

    # Whether to also generate an MP4
    make_video: bool = True

    # YouTube (auto-upload)
    youtube: Optional[YouTubeSettings] = None


class ArtifactLinks(BaseModel):
    mix_mp3: Optional[str] = None
    video_mp4: Optional[str] = None
    description_txt: Optional[str] = None
    thumbnail: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    stage: Optional[str] = None
    error: Optional[str] = None
    artifacts: ArtifactLinks = ArtifactLinks()
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None


