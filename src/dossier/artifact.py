"""Create a stable internal representation of transcripts.

Phase 1 — Artifact System

- Define artifact directory structure
- Define JSON schemas
    - Audio artifact
    - Chunk manifest
    - Chunk transcript
    - Final transcript
- Add artifact versioning
- Add artifact loading/saving
"""

from datetime import datetime
from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    """A single piece of transcribed speech (ex: a line)."""

    start: float
    end: float
    text: str
    track_id: str | None = None


class TranscriptTrack(BaseModel):
    """A source audio track."""

    id: str
    name: str | None = None


class ProcessingMetadata(BaseModel):
    """Information about how something was generated."""

    model: str
    compute_type: str
    device: str
    created_at: datetime


class AudioMetadata(BaseModel):
    """Information about the original audio."""

    source_file: str
    duration: float
    sample_rate: int


class Chunk(BaseModel):
    """A piece of audio to be processed."""

    id: str
    file: str
    start: float
    end: float


class ChunkManifest(BaseModel):
    """The result of splitting an audio file."""

    version: int = 1
    audio: AudioMetadata
    chunks: list[Chunk]


class ChunkTranscript(BaseModel):
    """Transcript generated from one chunk."""

    version: int = 1
    chunk: Chunk
    processing: ProcessingMetadata
    segments: list[TranscriptSegment]


class Transcript(BaseModel):
    """Final merged transcript."""

    version: int = 1
    audio: AudioMetadata
    processing: ProcessingMetadata
    tracks: list[TranscriptTrack]
    segments: list[TranscriptSegment]
