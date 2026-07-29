"""Dossier Recording Artifact."""

from datetime import UTC, datetime
from pathlib import Path

from pydantic import AliasChoices, BaseModel, Field

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
    working_path: Path
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

    @classmethod
    def _path(cls, recording_id: str) -> Path:
        return cls.resolve_static(recording_id, "recording.json")

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self._path(self.recording.id)

    def get_tracks(self) -> list[tuple[AudioTrack, Path]]:
        """Get the absolute paths to all tracks in this recording."""
        return [(track, self.resolve(track)) for track in self.audio.tracks]

    @classmethod
    def load(cls, recording_id: str) -> "RecordingArtifact":
        """Load a recording artifact from disk."""
        return super().load(recording_id)

    @property
    def id(self) -> str:
        """Get the recording ID."""
        return self.recording.id

    @property
    def name(self) -> str | None:
        """Get the recording name."""
        return self.recording.name or self.id
