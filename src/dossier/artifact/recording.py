"""Dossier Recording Artifact."""

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from dossier.artifact.base import Artifact, VersionedModel


class RecordingSource(BaseModel):
    """Original imported recording source."""

    filename: str
    size_bytes: int | None = None
    sha256: str | None = None
    original_path: str | None = None


class RecordingMetadata(VersionedModel):
    """Identity and metadata of a recording."""

    id: str
    name: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AudioTrack(BaseModel):
    """A normalized audio track."""

    id: str
    file: str
    channels: int = 1
    duration: float
    sample_rate: int


class AudioMetadata(BaseModel):
    """Normalized audio information."""

    recording_duration: float
    sample_rate: int
    tracks: list[AudioTrack]

    @property
    def track_count(self) -> int:
        """Number of audio tracks."""
        return len(self.tracks)


class RecordingArtifact(Artifact):
    """
    Root recording artifact.

    Stored as:

        recording.json
    """

    recording: RecordingMetadata
    source: RecordingSource
    audio: AudioMetadata

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self.workspace_path() / "recording.json"

    def get_tracks(self) -> list[tuple[AudioTrack, Path]]:
        """Get the absolute paths to all tracks in this recording."""
        return [(track, self.workspace_path() / track.file) for track in self.audio.tracks]

    @classmethod
    def load(cls, recording_id: str) -> "RecordingArtifact":
        """Load a recording artifact from disk."""
        from dossier.utils.storage import load_file

        path = cls.workspace_path_static(recording_id) / "recording.json"

        return load_file(path, cls)

    @property
    def id(self) -> str:
        """Get the recording ID."""
        return self.recording.id

    @property
    def name(self) -> str | None:
        """Get the recording name."""
        return self.recording.name or self.id
