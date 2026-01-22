from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .metadata import TrackInfo
from .timestamps import compute_track_timings, format_timestamp


def generate_edm_hashtags(extra_tags: Optional[List[str]] = None, max_tags: int = 15) -> str:
    base = [
        "#EDM",
        "#ElectronicMusic",
        "#DanceMusic",
        "#DJMix",
        "#Mix",
        "#HouseMusic",
        "#TechHouse",
        "#DeepHouse",
        "#ProgressiveHouse",
        "#Trance",
        "#Dubstep",
        "#DrumAndBass",
        "#FutureBass",
        "#Rave",
        "#Festival",
    ]

    if extra_tags:
        for t in extra_tags:
            t = (t or "").strip()
            if not t:
                continue
            if not t.startswith("#"):
                t = "#" + "".join(t.split())
            base.append(t)

    seen = set()
    uniq: List[str] = []
    for t in base:
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(t)

    return " ".join(uniq[:max_tags])


def build_tracklist_with_timestamps(tracks: List[TrackInfo], transition_ms: int = 6000) -> tuple[str, int]:
    durations = [t.duration_s for t in tracks]
    timings, total_s = compute_track_timings(durations, transition_ms=transition_ms)

    lines: List[str] = []
    for t, ti in zip(tracks, timings):
        ts = format_timestamp(ti.start_s)
        display = f"{t.artist} – {t.title}" if t.artist else t.title
        lines.append(f"{ts}  {display}")

    return "\n".join(lines), total_s


@dataclass(frozen=True)
class YouTubeDescriptionOptions:
    mixtape_title: str = "Smooth Fade EDM Mixtape"
    shuffle: bool = True
    transition_ms: int = 6000
    include_disclaimer: bool = True
    extra_hashtags: Optional[List[str]] = None


def generate_youtube_description(folder_tracks: List[TrackInfo], opts: YouTubeDescriptionOptions) -> str:
    tracklist, total_s = build_tracklist_with_timestamps(folder_tracks, transition_ms=opts.transition_ms)
    total_len = format_timestamp(total_s)
    hashtags = generate_edm_hashtags(extra_tags=opts.extra_hashtags)

    intro = (
        f"{opts.mixtape_title}\n\n"
        f"A seamless EDM listening session with smooth crossfades (~{opts.transition_ms/1000:.1f}s) "
        f"built from my current rotation. Put this on for focus, driving, gym, or late-night vibes.\n\n"
        f"Total length: {total_len}\n"
    )

    tips = "\n🧠 Tip: If you like a particular track, drop the timestamp in the comments and I’ll pin it.\n"

    disclaimer = ""
    if opts.include_disclaimer:
        disclaimer = (
            "\n\n⚠️ Disclaimer:\n"
            "Track credits belong to their respective owners. If you’re a rights holder and want changes, "
            "reach out and I’ll respond quickly.\n"
        )

    return (
        intro
        + "\n🎵 Tracklist:\n"
        + tracklist
        + tips
        + disclaimer
        + "\n\n"
        + hashtags
    )


