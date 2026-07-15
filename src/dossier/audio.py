"""Processes the initial audio file into a digestible format for the model to consume."""

import math
from pathlib import Path
import subprocess
from orjson import loads as json_loads
from typing import Any, TypedDict

from rich.progress import Progress

from dossier.utils.dir import REPO_ROOT

FFPROBE = REPO_ROOT / "ffmpeg" / "bin" / "ffprobe.exe"
FFMPEG = REPO_ROOT / "ffmpeg" / "bin" / "ffmpeg.exe"

class AudioStream(TypedDict):
    """Represents an audio stream in the input file."""

    index: int
    codec_name: str
    sample_rate: int
    channels: int


def run_ffmpeg(*args: str) -> subprocess.CompletedProcess[bytes]:
    """Run ffmpeg with the provided arguments."""
    return subprocess.run(
        [FFMPEG, *args],
        check=True,
        capture_output=True,
    )


def run_ffprobe(*args: str) -> subprocess.CompletedProcess[bytes]:
    """Run ffprobe with the provided arguments."""
    result =  subprocess.run(
        [FFPROBE, *args],
        check=True,
        capture_output=True,
    )

    if result.returncode != 0:
            print(result.stderr.decode())
            result.check_returncode()

    return result

def probe_audio_streams(input_file: Path) -> list[AudioStream]:
    """Probe the audio streams of the input file."""
    result = run_ffprobe(
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index,codec_name,sample_rate,channels",
        "-of",
        "json",
        str(input_file),
    )

    data:  dict[str, Any]= json_loads(result.stdout)

    return [
        {
            "index": stream["index"],
            "codec_name": stream["codec_name"],
            "sample_rate": int(stream["sample_rate"]),
            "channels": stream["channels"],
        }
        for stream in data["streams"]
    ]


def probe_duration(input_file: Path) -> float:
    """Get the duration of a media file in seconds."""
    result = run_ffprobe(
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(input_file),
    )

    data = json_loads(result.stdout)

    return float(data["format"]["duration"])

def split_audio(
    input_file: Path,
    output_dir: Path,
    duration: float,
    chunk_minutes: int,
    overlap_seconds: int,
    sample_rate: int,
) -> list[Path]:
    """Split the input audio file into overlapping chunks."""
    output_dir.mkdir(parents=True, exist_ok=True)

    chunk_seconds = chunk_minutes * 60
    step_seconds = chunk_seconds - overlap_seconds

    total_chunks = math.ceil(duration / step_seconds)

    chunks: list[Path] = []

    with Progress() as progress:
        task = progress.add_task(
            (
                f"Splitting audio into {total_chunks} chunks "
                f"(Chunk size: {chunk_minutes} minutes, "
                f"Overlap: {overlap_seconds} seconds)"
            ),
            total=total_chunks,
        )

        for index in range(total_chunks):
            start = index * step_seconds

            if start >= duration:
                break

            output = output_dir / f"chunk_{index:03d}.wav"

            run_ffmpeg(
                "-ss",
                str(start),
                "-i",
                str(input_file),
                "-t",
                str(chunk_seconds),
                "-vn",
                "-map",
                "0:a:0",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-c:a",
                "pcm_s16le",
                str(output),
            )

            chunks.append(output)
            progress.advance(task)

    return chunks



def process_recording(
    input_file: Path,
    output_dir: Path,
    chunk_minutes: int,
    overlap_seconds: int,
    sample_rate: int,
) -> list[Path]:
    """Process the input recording into overlapping audio chunks."""
    # streams = probe_audio_streams(input_file) # TODO: handle mullti-stream recordings
    duration = probe_duration(input_file)

    return split_audio(
        input_file,
        output_dir,
        duration,
        chunk_minutes=chunk_minutes,
        overlap_seconds=overlap_seconds,
        sample_rate=sample_rate,
    )
