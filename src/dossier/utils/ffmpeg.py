"""Utilities for running ffmpeg and ffprobe commands."""

import subprocess

from dossier.utils.dir import FFMPEG, FFPROBE


def run_ffmpeg(*args: str) -> subprocess.CompletedProcess[bytes]:
    """Run ffmpeg with the provided arguments."""
    try:
        return subprocess.run(
            [FFMPEG, "-hide_banner", "-y", *args],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.decode())
        raise


def run_ffprobe(*args: str) -> subprocess.CompletedProcess[bytes]:
    """Run ffprobe with the provided arguments."""
    try:
        return subprocess.run(
            [FFPROBE, *args],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.decode())
        raise
