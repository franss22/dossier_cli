"""Processes the initial audio file into a digestible format for the model to consume."""

import math
from pathlib import Path
import subprocess
from orjson import loads as json_loads
from typing import Any
from dossier.utils.types import AudioStream, AudioChunk

from rich.progress import Progress


def split_audio(
    input_file: Path,
    output_dir: Path,
    duration: float,
    chunk_minutes: int,
    overlap_seconds: int,
    sample_rate: int,
) -> list[AudioChunk]:
    """Split the input audio file into overlapping chunks."""
    output_dir.mkdir(parents=True, exist_ok=True)

    chunk_seconds = chunk_minutes * 60
    step_seconds = chunk_seconds - overlap_seconds

    total_chunks = math.ceil(duration / step_seconds)

    chunks: list[AudioChunk] = []

    with Progress() as progress:
        task = progress.add_task(
            (
                f"Splitting audio into {total_chunks} chunks "
                f"(Chunk size: {chunk_minutes} minutes, "
                f"Overlap: {overlap_seconds} seconds)"
            ),
            total=total_chunks,
        )

        for index in range(min(total_chunks, 1)):  # TODO: Remove the `min` function to process all chunks
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
            chunks.append(AudioChunk(path=output, start_time=start, duration=min(chunk_seconds, duration - start)))

            progress.advance(task)

    return chunks


def process_recording(
    input_file: Path,
    output_dir: Path,
    chunk_minutes: int,
    overlap_seconds: int,
    sample_rate: int,
) -> list[AudioChunk]:
    """Process the input recording into overlapping audio chunks."""
    # streams = probe_audio_streams(input_file) # TODO: handle multi-stream recordings
    duration = probe_duration(input_file)

    return split_audio(
        input_file,
        output_dir,
        duration,
        chunk_minutes=chunk_minutes,
        overlap_seconds=overlap_seconds,
        sample_rate=sample_rate,
    )
