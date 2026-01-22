from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional, Tuple


try:
    from mutagen import File as MutagenFile
except Exception:  # pragma: no cover
    MutagenFile = None


AUDIO_EXTS = (".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg")


@dataclass(frozen=True)
class TrackInfo:
    filename: str
    title: str
    artist: Optional[str]
    duration_s: int
    path: str


def sanitize_filename_to_title(name: str) -> str:
    """Fallback: '01 - Artist - Track (Remix).mp3' -> 'Artist - Track (Remix)'."""
    base = os.path.splitext(os.path.basename(name))[0]
    base = re.sub(r"^\s*\d+\s*[-_. ]\s*", "", base)  # strip leading track number
    base = re.sub(r"\s+", " ", base).strip()
    return base


def read_tags_and_duration(path: str) -> Tuple[str, Optional[str], int]:
    """Return (title, artist, duration_s) using mutagen when available."""
    fallback_title = sanitize_filename_to_title(path)
    fallback_artist = None

    if MutagenFile is None:
        return fallback_title, fallback_artist, 0

    audio = MutagenFile(path, easy=True)
    if audio is None:
        return fallback_title, fallback_artist, 0

    duration_s = 0
    try:
        duration_s = int(audio.info.length)  # type: ignore[attr-defined]
    except Exception:
        duration_s = 0

    title = fallback_title
    artist = None
    try:
        if audio.tags:  # type: ignore[truthy-bool]
            t = audio.tags.get("title", [None])[0]  # type: ignore[union-attr]
            a = audio.tags.get("artist", [None])[0]  # type: ignore[union-attr]
            if t:
                title = str(t).strip()
            if a:
                artist = str(a).strip()
    except Exception:
        pass

    return title, artist, duration_s


def load_tracks_from_folder(folder: str, shuffle: bool = False) -> list[TrackInfo]:
    import random

    files = [f for f in os.listdir(folder) if f.lower().endswith(AUDIO_EXTS)]
    files.sort()
    if shuffle:
        random.shuffle(files)

    tracks: list[TrackInfo] = []
    for f in files:
        path = os.path.join(folder, f)
        title, artist, duration_s = read_tags_and_duration(path)
        tracks.append(TrackInfo(filename=f, title=title, artist=artist, duration_s=duration_s, path=path))
    return tracks


