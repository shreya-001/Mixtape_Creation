from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, List, Optional

from pydub import AudioSegment


@dataclass(frozen=True)
class MixResult:
    output_path: str
    duration_ms: int
    track_paths: List[str]


def build_crossfaded_mixtape(
    track_paths: Iterable[str],
    output_path: str,
    transition_ms: int = 6000,
    sample_rate: int = 44100,
    channels: int = 2,
    lowpass_hz: int = 4000,
) -> MixResult:
    """Build a single MP3 mix from multiple audio files using crossfades.

    This mirrors the notebook logic:
      overlap = min(transition_ms, len(song), len(mixtape_so_far))
      outro = mixtape[-overlap:].fade_out(overlap).low_pass_filter(lowpass_hz)
      intro = song[:overlap].fade_in(overlap).low_pass_filter(lowpass_hz)
      transition = outro.overlay(intro)
      mixtape = mixtape[:-overlap] + transition + song[overlap:]
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    paths = [p for p in track_paths if p]
    if not paths:
        raise ValueError("No track paths provided.")

    mixtape: Optional[AudioSegment] = None

    for p in paths:
        song = AudioSegment.from_file(p)
        song = song.set_channels(channels).set_frame_rate(sample_rate)

        if mixtape is None:
            mixtape = song
            continue

        overlap = min(int(transition_ms), len(song), len(mixtape))
        if overlap <= 0:
            mixtape = mixtape + song
            continue

        outro = mixtape[-overlap:].fade_out(overlap).low_pass_filter(lowpass_hz)
        intro = song[:overlap].fade_in(overlap).low_pass_filter(lowpass_hz)
        transition = outro.overlay(intro)
        mixtape = mixtape[:-overlap] + transition + song[overlap:]

    assert mixtape is not None
    mixtape.export(output_path, format="mp3")

    return MixResult(output_path=output_path, duration_ms=len(mixtape), track_paths=paths)


