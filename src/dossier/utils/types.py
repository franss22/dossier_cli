"""Common type definitions."""

from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class AudioStream(TypedDict):
    """Represents an audio stream in the input file."""

    index: int
    codec_name: str
    sample_rate: int
    channels: int


@dataclass(slots=True)
class AudioChunk:
    """Represents a chunk of audio extracted from the input file."""

    path: Path
    start_time: float
    duration: float


@dataclass(slots=True)
class Segment:
    """Represents a segment of transcribed audio.

    ```
    0.00 → 4.82   "Welcome back..."
    4.82 → 9.15   "Last session..."
    9.15 → 13.01  "You entered the hotel..."
    ```
    """

    start: float
    end: float
    text: str
    speaker: str | None


TranscribedChunk = list[Segment]
