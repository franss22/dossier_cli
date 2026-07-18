"""Chunk transcript artifacts.

A chunk transcript represents the output of transcribing
one audio chunk from one track.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dossier.artifact.base import Artifact
from dossier.artifact.transcripts.run import DecoderConfiguration, TranscriptionRun

from .segment import TranscriptSegment


class ChunkSource(BaseModel):
    """Information about the audio chunk that produced this transcript."""

    track_id: str
    chunk_id: str
    chunk_index: int

    start: float
    end: float
    duration: float

    overlap_before: float = 0.0
    overlap_after: float = 0.0


class ChunkTranscriptMetrics(BaseModel):
    """
    Aggregated quality indicators for a chunk.

    These are computed after transcription and allow
    quick inspection without loading all segments.
    """

    raw_segment_count: int = 0
    kept_segment_count: int = 0
    discarded_segment_count: int = 0

    processing_time: float | None = None
    cpu_time: float | None = None
    realtime_factor: float | None = None

    speech_duration: float = 0.0

    average_logprob: float | None = None
    worst_logprob: float | None = None

    max_compression_ratio: float | None = None

    average_no_speech_probability: float | None = None

    suspicious_segments: int = 0


class ChunkDebugInfo(BaseModel):
    """Runtime information about processing this chunk."""

    versions: dict[str, str] = Field(default_factory=dict)
    transcription_info: dict[str, Any] = Field(default_factory=dict)
    """Info values returned by the model decoder, e.g. `segments, info` from Faster Whisper."""


class ChunkTranscriptArtifact(Artifact):
    """
    Transcript generated from a single audio chunk.

    Stored as:

        transcriptions/{transcription_id}/{chunk_id}_chunk_transcript.json

    The chunk contains its own decoder snapshot and metrics
    so it remains reproducible even without the run manifest.
    """

    track_id: str
    chunk_id: str
    chunk_index: int

    transcription: TranscriptionRun
    source: ChunkSource
    decoder: DecoderConfiguration

    metrics: ChunkTranscriptMetrics = Field(default_factory=ChunkTranscriptMetrics)

    diagnostics: ChunkDebugInfo = Field(default_factory=ChunkDebugInfo)

    segments: list[TranscriptSegment] = Field(default_factory=list)

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return (
            self.workspace_path() / "transcriptions" / self.transcription.id / f"{self.chunk_id}_chunk_transcript.json"
        )

    @classmethod
    def load(
        cls,
        recording_id: str,
        transcription_id: str,
        chunk_id: str,
    ) -> "ChunkTranscriptArtifact":
        """Load a chunk transcript artifact from disk."""
        from dossier.utils.storage import load_file

        path = (
            cls.workspace_path_static(recording_id)
            / "transcriptions"
            / transcription_id
            / f"{chunk_id}_chunk_transcript.json"
        )

        return load_file(path, cls)


ChunkTranscriptArtifact.model_rebuild()
