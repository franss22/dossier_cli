"""Transcription artifacts for a processing run.

TranscriptionRunArtifact
│
├── TranscriptionRun
│   ├── id
│   ├── stage
│   ├── model
│   ├── compute_type
│   ├── device
│   ├── created_at
│   └── processing_time
│
├── chunk_states{}
│   key:
│       "{track_id}/{chunk_id}"
│
│   value:
│       ChunkTranscriptionState
│       ├── track_id
│       ├── chunk_id
│       ├── chunk_index
│       ├── completed
│       ├── started_at
│       ├── completed_at
│       └── error
│
├── tracks[]
│   └── TranscriptTrack
│       ├── id
│       └── name
│
└── chunking
    └── ChunkSetConfiguration


ChunkTranscriptArtifact
│
├── TranscriptionRun
│
├── track_id
├── chunk_id
├── chunk_index
│
└── segments[]
    └── TranscriptSegment
        ├── start
        ├── end
        ├── text
        ├── track_id
        ├── chunk_id
        ├── chunk_index
        └── transcription_id


MergedTranscriptArtifact
│
├── RecordingMetadata
│
├── TranscriptionRun
│
├── tracks[]
│   └── TranscriptTrack
│
└── segments[]
    └── TranscriptSegment
        ├── start
        ├── end
        ├── text
        ├── track_id
        ├── chunk_id
        ├── chunk_index
        └── transcription_id
"""

import secrets
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field
from slugify import slugify

from dossier.artifact.base import Artifact
from dossier.artifact.chunks import ChunkSetConfiguration
from dossier.artifact.recording import RecordingMetadata
from dossier.utils.config import get_config


class TranscriptionRun(BaseModel):
    """Used configuration and useful metadata for a single pipeline execution."""

    id: str

    stage: str

    model: str | None = None
    compute_type: str | None = None
    device: str | None = None
    language: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    processing_time: float | None = None

    @classmethod
    def build_id(cls, model: str, device: str) -> str:
        """Build a transcription run ID from model and device."""
        return "_".join([
            slugify(model),
            slugify(device),
            datetime.now(UTC).strftime("%Y%m%d"),
            secrets.token_hex(4),
        ])

    @classmethod
    def create(
        cls,
        stage: str,
        model: str | None = None,
        compute_type: str | None = None,
        device: str | None = None,
        language: str | None = None,
    ) -> "TranscriptionRun":
        """Create a new transcription run with a unique ID."""
        config = get_config()
        model = model or config.transcription.model_size
        compute_type = compute_type or config.transcription.compute_type
        device = device or config.transcription.device
        language = language or config.transcription.language

        return cls(
            id=cls.build_id(model, device),
            stage=stage,
            model=model,
            compute_type=compute_type,
            device=device,
        )


class TranscriptTrack(BaseModel):
    """Logical transcript track."""

    id: str
    name: str | None = None


class TranscriptSegment(BaseModel):
    """A single transcribed speech segment."""

    start: float
    end: float

    text: str

    # Source track
    track_id: str

    # Provenance
    chunk_id: str
    chunk_index: int
    transcription_id: str


class ChunkTranscriptionState(BaseModel):
    """Processing status for a chunk."""

    completed: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
    track_id: str
    chunk_id: str
    chunk_index: int

    error: str | None = None

    def load_chunk(self, recording_id: str, transcription_id: str) -> "ChunkTranscriptArtifact":
        """Load the chunk transcript artifact from disk."""
        from dossier.artifact.transcript import ChunkTranscriptArtifact

        if not self.completed:
            raise ValueError("Cannot load chunk transcript: chunk is not completed.")

        return ChunkTranscriptArtifact.load(
            recording_id=recording_id,
            transcription_id=transcription_id,
            chunk_id=self.chunk_id,
        )


class ChunkTranscriptArtifact(Artifact):
    """
    Transcript generated from one audio chunk.

    Stored as:

        transcriptions/{transcription_id}/{track_id}/{chunk_id}.json
    """

    track_id: str
    chunk_id: str
    chunk_index: int

    transcription: TranscriptionRun

    segments: list[TranscriptSegment]

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return (
            self.workspace_path() / "transcriptions" / self.transcription.id / f"{self.chunk_id}_chunk_transcript.json"
        )  # chunk_id includes track

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


class TranscriptionRunArtifact(Artifact):
    """
    Manifest for a transcription processing run.

    Stored as:

        transcripts/{transcription_id}/transcript_run.json
    """

    # Key format:
    #
    #   {track_id}/{chunk_id}
    #
    # Example:
    #
    #   "1-b1rdest/chunk_000"
    #
    chunk_states: dict[str, ChunkTranscriptionState]
    chunk_configuration: ChunkSetConfiguration
    tracks: list[TranscriptTrack] = Field(default_factory=list)
    transcription: TranscriptionRun

    merged: bool = False

    started_at: datetime | None = None
    completed_at: datetime | None = None

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self.workspace_path() / "transcriptions" / self.transcription.id / "transcription_manifest.json"

    @classmethod
    def load(
        cls,
        recording_id: str,
        transcription_id: str,
    ) -> "TranscriptionRunArtifact":
        """Load a transcript manifest artifact from disk."""
        from dossier.utils.storage import load_file

        path = (
            cls.workspace_path_static(recording_id)
            / "transcriptions"
            / transcription_id
            / "transcription_manifest.json"
        )

        return load_file(path, cls)

    def get_track_chunks(self, track_id: str) -> dict[str, ChunkTranscriptionState]:
        """Get all chunks for a specific track."""
        return {key: state for key, state in self.chunk_states.items() if key.startswith(f"{track_id}/")}

    @classmethod
    def list(cls, recording_id: str) -> list["TranscriptionRunArtifact"]:
        """List all merged transcript artifacts for a given recording."""
        directory = cls.workspace_path_static(recording_id) / "transcriptions"

        if not directory.exists():
            return []

        return [
            cls.load(recording_id, folder.name)
            for folder in directory.iterdir()
            if folder.is_dir() and (folder / "transcription_manifest.json").exists()
        ]


class MergedTranscriptArtifact(Artifact):
    """
    Final merged transcript.

    Stored as:

        transcript.json
    """

    recording: RecordingMetadata

    tracks: list[TranscriptTrack] = Field(default_factory=list)

    transcription: TranscriptionRun

    segments: list[TranscriptSegment]

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self.workspace_path() / "merged_transcriptions" / self.transcription.id / "merged_transcript.json"

    @classmethod
    def load(cls, recording_id: str, transcription_id: str) -> "MergedTranscriptArtifact":
        """Load a final merged transcript artifact from disk."""
        from dossier.utils.storage import load_file

        path = (
            cls.workspace_path_static(recording_id)
            / "merged_transcriptions"
            / transcription_id
            / "merged_transcript.json"
        )

        return load_file(path, cls)
