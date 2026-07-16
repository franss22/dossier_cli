"""Dossier Recording Artifact."""

from pydantic import BaseModel, Field
from datetime import UTC, datetime
from pathlib import Path
from dossier.artifact.base import Artifact

from dossier.artifact.base import VersionedModel


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


class RecordingArtifact(Artifact):
    """
    Root recording artifact.

    Stored as:

        recording.json
    """

    recording: RecordingMetadata
    source: RecordingSource
    tracks: list[str] = Field(default_factory=list)

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self.workspace_path() / "recording.json"
