from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple


def format_timestamp(total_seconds: int) -> str:
    """Format seconds as YouTube-friendly timestamp.

    - < 1 hour: M:SS
    - >= 1 hour: H:MM:SS
    """
    if total_seconds < 0:
        total_seconds = 0
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:d}:{s:02d}"


@dataclass(frozen=True)
class TrackTiming:
    index: int
    start_s: int
    duration_s: int


def compute_track_timings(
    durations_s: Iterable[int],
    transition_ms: int = 6000,
) -> Tuple[List[TrackTiming], int]:
    """Compute track start times for a crossfaded mix.

    We approximate the overlap per transition as:
      overlap_s = min(transition_s, prev_duration_s, current_duration_s)

    Track i starts at the current cursor (mix time).
    Cursor advances by (current_duration_s - overlap_s).

    Returns: (timings, total_duration_s)
    """
    transition_s = max(0.0, transition_ms / 1000.0)
    timings: List[TrackTiming] = []

    cursor_s: float = 0.0
    prev_dur: int | None = None

    for idx, d in enumerate(durations_s, start=1):
        dur = max(0, int(d))
        timings.append(TrackTiming(index=idx, start_s=int(cursor_s), duration_s=dur))

        if prev_dur is None:
            cursor_s += float(dur)
        else:
            overlap = min(transition_s, float(prev_dur), float(dur))
            cursor_s += max(0.0, float(dur) - overlap)

        prev_dur = dur

    return timings, int(cursor_s)


