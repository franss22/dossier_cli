"""Transcription artifacts for a processing run."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from pathlib import Path
from dossier.artifact.base import Artifact
from dossier.artifact.chunks import ChunkMetadata, ChunkingConfiguration
from dossier.artifact.audio import AudioMetadata
from dossier.artifact.recording import RecordingMetadata


class ProcessingRun(BaseModel):
    """A single pipeline execution."""

    id: str

    stage: str

    model: str | None = None
    compute_type: str | None = None
    device: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    processing_time: float | None = None


class TranscriptTrack(BaseModel):
    """Logical transcript track."""

    id: str
    name: str | None = None


class TranscriptSegment(BaseModel):
    """A single transcribed speech segment."""

    start: float
    end: float

    text: str

    track_id: str | None = None

    # Provenance
    chunk_id: str
    processing_id: str


class TranscriptChunkStatus(BaseModel):
    """Processing status for a chunk."""

    chunk_id: str
    completed: bool = False


class TranscriptManifestArtifact(Artifact):
    """
    Manifest for a transcription processing run.

    Stored as:

        transcripts/{processing_id}/manifest.json
    """

    chunking: ChunkingConfiguration
    processing: ProcessingRun

    expected_chunks: int

    chunks: list[TranscriptChunkStatus]

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self.workspace_path() / "transcripts" / self.processing.id / "manifest.json"

    @classmethod
    def load(cls, recording_id: str, processing_id: str) -> "TranscriptManifestArtifact":
        """Load a transcript manifest artifact from disk."""
        from dossier.storage import load_file

        path = cls.workspace_path_static(recording_id) / "transcripts" / processing_id / "manifest.json"

        return load_file(path, cls)


class ChunkTranscriptArtifact(Artifact):
    """
    Transcript generated from one chunk.

    Stored as:

        transcripts/{processing_id}/{chunk_id}.json
    """

    chunk: ChunkMetadata
    processing: ProcessingRun

    segments: list[TranscriptSegment]

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self.workspace_path() / "transcripts" / self.processing.id / f"{self.chunk.id}.json"

    @classmethod
    def load(cls, recording_id: str, processing_id: str, chunk_id: str) -> "ChunkTranscriptArtifact":
        """Load a chunk transcript artifact from disk."""
        from dossier.storage import load_file

        path = cls.workspace_path_static(recording_id) / "transcripts" / processing_id / f"{chunk_id}.json"

        return load_file(path, cls)


class TranscriptArtifact(Artifact):
    """
    Final merged transcript.

    Stored as:

        transcript.json
    """

    recording: RecordingMetadata

    audio: AudioMetadata

    tracks: list[TranscriptTrack] = Field(default_factory=list)

    chunks: list[ChunkMetadata]

    processing_runs: list[ProcessingRun]

    segments: list[TranscriptSegment]

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self.workspace_path() / "transcript.json"

    @classmethod
    def load(cls, recording_id: str) -> "TranscriptArtifact":
        """Load a final merged transcript artifact from disk."""
        from dossier.storage import load_file

        path = cls.workspace_path_static(recording_id) / "transcript.json"

        return load_file(path, cls)
