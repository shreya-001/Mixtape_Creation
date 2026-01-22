from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from PIL import Image


@dataclass(frozen=True)
class VideoRenderOptions:
    video_resolution: Tuple[int, int] = (1280, 720)
    fps: int = 1
    preset: str = "ultrafast"


def make_video_from_audio(
    image_path: str,
    audio_path: str,
    output_path: str,
    opts: VideoRenderOptions = VideoRenderOptions(),
) -> str:
    """Create an MP4 video by looping a background image over an audio track.

    Requires ffmpeg installed and available on PATH.
    Mirrors the notebook approach but uses a temp resized image.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        resized = str(Path(td) / "bg_resized.jpg")
        img = Image.open(image_path)
        # Ensure the image is in an ffmpeg/JPEG-friendly mode (RGB).
        if img.mode != "RGB":
            img = img.convert("RGB")
        img = img.resize(opts.video_resolution)
        img.save(resized, format="JPEG", quality=95)

        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            resized,
            "-i",
            audio_path,
            "-c:v",
            "libx264",
            "-preset",
            opts.preset,
            "-tune",
            "stillimage",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(int(opts.fps)),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            output_path,
        ]

        subprocess.run(cmd, check=True)

    return output_path


