"""Utilities for running ffmpeg and ffprobe commands."""

import os
import subprocess
from pathlib import Path

from dossier.utils.dir import FFMPEG, FFPROBE, REPO_ROOT

os.environ["PATH"] += os.pathsep + str(REPO_ROOT / "ffmpeg" / "bin")

FFmpegArg = str | os.PathLike[str] | int | float


def run_ffmpeg(*args: FFmpegArg) -> subprocess.CompletedProcess[bytes]:
    """Run ffmpeg with the provided arguments, which can be str or Path."""
    try:
        return subprocess.run(
            [FFMPEG, "-hide_banner", "-y", *(str(arg) for arg in args)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.decode())
        raise


def run_ffprobe(*args: FFmpegArg) -> subprocess.CompletedProcess[bytes]:
    """Run ffprobe with the provided arguments."""
    try:
        return subprocess.run(
            [FFPROBE, *(str(arg) for arg in args)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.decode())
        raise


def segment(
    input_file: Path,
    output_file: Path,
    start: float,
    end: float,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
) -> None:
    """
    Extract a segment from an audio file and save it as a normalized WAV.

    Args:
        input_file: Source audio file.
        output_file: Destination WAV file.
        start: Segment start time in seconds.
        end: Segment end time in seconds (exclusive).
        sample_rate: Output sample rate in Hz.
        channels: Number of output audio channels.
    """
    if end <= start:
        raise ValueError("Segment end time must be greater than start time.")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    run_ffmpeg(
        "-ss",
        start,
        "-i",
        input_file,
        "-t",
        end - start,
        "-vn",
        "-map",
        "0:a:0",
        "-ac",
        channels,
        "-ar",
        sample_rate,
        "-c:a",
        "pcm_s16le",
        output_file,
    )


def duration(input_file: os.PathLike[str]) -> float:
    """Get the duration of an audio file in seconds."""
    result = run_ffprobe(
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_file),
    )
    return float(result.stdout.decode().strip())


FFMPEG_VERSION = run_ffmpeg("-version").stdout.decode().splitlines()[0]
FFPROBE_VERSION = run_ffprobe("-version").stdout.decode().splitlines()[0]
