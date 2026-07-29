"""Transcription run artifacts.

Contains:
- decoder configuration
- transcription execution metadata
- chunk processing state
- transcription manifest artifact
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from dossier.artifact.base import Artifact
from dossier.artifact.chunks import ChunkSetConfiguration
from dossier.artifact.transcripts.chunk import ChunkTranscriptArtifact
from dossier.artifact.transcripts.run import TranscriptionRun


class ChunkTranscriptionState(BaseModel):
    """Processing state for a single chunk."""

    completed: bool = False

    started_at: datetime | None = None

    completed_at: datetime | None = None

    track_id: str

    chunk_id: str

    chunk_index: int

    error: str | None = None

    def load_chunk(
        self,
        recording_id: str,
        transcription_id: str,
    ) -> ChunkTranscriptArtifact:
        """Load this chunk's transcript artifact."""
        from .chunk import ChunkTranscriptArtifact

        if not self.completed:
            raise ValueError("Cannot load chunk transcript: chunk is not completed.")

        return ChunkTranscriptArtifact.load(
            recording_id=recording_id,
            transcription_id=transcription_id,
            chunk_id=self.chunk_id,
        )


class TranscriptTrack(BaseModel):
    """Logical transcript track."""

    id: str

    name: str | None = None


class TranscriptionRunArtifact(Artifact):
    """
    Manifest for a transcription execution.

    Stored as:

        transcriptions/{transcription_id}/transcription_manifest.json
    """

    chunk_states: dict[str, ChunkTranscriptionState]

    chunk_configuration: ChunkSetConfiguration

    tracks: list[TranscriptTrack] = Field(default_factory=list)

    transcription: TranscriptionRun

    compiled: bool = False

    started_at: datetime | None = None

    completed_at: datetime | None = None

    @classmethod
    def _path(
        cls,
        recording_id: str,
        transcription_id: str,
    ) -> Path:
        return (
            cls.workspace_path_static(recording_id)
            / "transcriptions"
            / transcription_id
            / "transcription_manifest.json"
        )

    def storage_path(self) -> Path:
        """Exact storage location."""
        return self._path(self.metadata.recording_id, self.transcription.id)

    @classmethod
    def load(
        cls,
        recording_id: str,
        transcription_id: str,
    ) -> "TranscriptionRunArtifact":
        """Load transcription manifest."""
        return super().load(recording_id, transcription_id)

    def get_track_chunks(
        self,
        track_id: str,
    ) -> dict[str, ChunkTranscriptionState]:
        """Get all chunks belonging to a track."""
        return {key: state for key, state in self.chunk_states.items() if key.startswith(f"{track_id}/")}

    def load_track_chunks(
        self,
        track_id: str,
    ) -> list[ChunkTranscriptArtifact]:
        """Load all chunk transcript artifacts for a given track."""
        chunk_states = self.get_track_chunks(track_id)

        if any(not state.completed for state in chunk_states.values()):
            raise ValueError(f"Cannot load track {track_id}: not all chunks are completed.")

        return sorted(
            (
                state.load_chunk(
                    recording_id=self.metadata.recording_id,
                    transcription_id=self.transcription.id,
                )
                for state in chunk_states.values()
            ),
            key=lambda chunk: chunk.chunk_index,
        )

    @classmethod
    def list(
        cls,
        recording_id: str,
    ) -> list["TranscriptionRunArtifact"]:
        """List all transcription runs."""
        directory = cls.workspace_path_static(recording_id) / "transcriptions"

        if not directory.exists():
            return []

        return [
            cls.load(recording_id, folder.name)
            for folder in directory.iterdir()
            if (folder.is_dir() and (folder / "transcription_manifest.json").exists())
        ]
