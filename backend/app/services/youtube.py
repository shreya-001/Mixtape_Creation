from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# OAuthLib will error if the returned token scopes include more than requested.
# Because Google may include OpenID/userinfo scopes (e.g. if the user previously
# granted them during login), we request the superset here.
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    # Read and upload permissions for YouTube so we can both upload videos
    # and fetch the connected channel info.
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
]


@dataclass(frozen=True)
class YouTubeUploadResult:
    video_id: str
    url: str


def _save_credentials(creds: Credentials, token_path: Path) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")


def load_credentials(token_path: Path) -> Optional[Credentials]:
    if not token_path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_credentials(creds, token_path)
    return creds


def is_authorized(token_path: Path) -> bool:
    creds = load_credentials(token_path)
    return bool(creds and creds.valid)


def build_oauth_authorization_url(
    client_secrets_path: Path,
    redirect_uri: str,
    state: str,
) -> Tuple[str, str]:
    flow = Flow.from_client_secrets_file(
        str(client_secrets_path),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return auth_url, state


def exchange_code_for_token(
    client_secrets_path: Path,
    redirect_uri: str,
    code: str,
    token_path: Path,
) -> None:
    flow = Flow.from_client_secrets_file(
        str(client_secrets_path),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    _save_credentials(creds, token_path)


def exchange_code_for_token_json(
    client_secrets_path: Path,
    redirect_uri: str,
    code: str,
) -> str:
    """Exchange OAuth code for a token JSON string (to store per-user in DB)."""
    flow = Flow.from_client_secrets_file(
        str(client_secrets_path),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    # Be tolerant of scope supersets in token response.
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    flow.fetch_token(code=code)
    creds = flow.credentials
    return creds.to_json()


def _youtube_client(creds: Credentials):
    return build("youtube", "v3", credentials=creds)


def get_my_channel(
    token_json: str,
    *,
    on_token_json_updated: Optional[Callable[[str], None]] = None,
) -> dict:
    """Return basic info about the connected YouTube channel for this token."""
    creds = credentials_from_token_json(token_json, on_token_json_updated=on_token_json_updated)
    if not creds or not creds.valid:
        raise RuntimeError("Invalid YouTube credentials")
    youtube = _youtube_client(creds)
    resp = youtube.channels().list(part="snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError("No YouTube channel found for this account")
    ch = items[0]
    return {
        "channel_id": ch.get("id"),
        "title": (ch.get("snippet") or {}).get("title"),
    }


def credentials_from_token_json(
    token_json: str,
    *,
    on_token_json_updated: Optional[Callable[[str], None]] = None,
) -> Credentials:
    data = json.loads(token_json)
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Important: persist refreshed token state if the caller provides a hook.
        # Without this, every subsequent API call after access_token expiry will
        # redundantly refresh against Google (wasteful + rate-limit risk).
        if on_token_json_updated is not None:
            on_token_json_updated(creds.to_json())
    return creds


def upload_video_with_token_json(
    *,
    token_json: str,
    video_path: Path,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: str = "unlisted",
    thumbnail_path: Optional[Path] = None,
    on_token_json_updated: Optional[Callable[[str], None]] = None,
) -> YouTubeUploadResult:
    creds = credentials_from_token_json(token_json, on_token_json_updated=on_token_json_updated)
    if not creds or not creds.valid:
        raise RuntimeError("Invalid YouTube credentials")
    youtube = _youtube_client(creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "10",
        },
        "status": {"privacyStatus": privacy_status},
    }

    media = MediaFileUpload(str(video_path), mimetype="video/*", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response["id"]

    if thumbnail_path and thumbnail_path.exists():
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/*"),
        ).execute()

    return YouTubeUploadResult(video_id=video_id, url=f"https://www.youtube.com/watch?v={video_id}")


def upload_video(
    *,
    token_path: Path,
    video_path: Path,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: str = "unlisted",
    thumbnail_path: Optional[Path] = None,
) -> YouTubeUploadResult:
    creds = load_credentials(token_path)
    if not creds or not creds.valid:
        raise RuntimeError("YouTube is not authorized. Run OAuth first.")

    youtube = _youtube_client(creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "10",  # Music
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }

    media = MediaFileUpload(str(video_path), mimetype="video/*", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        # (Optional) could expose upload progress via callback

    video_id = response["id"]

    if thumbnail_path and thumbnail_path.exists():
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/*"),
        ).execute()

    return YouTubeUploadResult(video_id=video_id, url=f"https://www.youtube.com/watch?v={video_id}")


