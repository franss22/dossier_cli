"""Base classes for artifacts.

Artifacts are persisted objects that represent the state of a recording at a given point in time.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from pathlib import Path

from dossier.utils.dir import STORAGE_ROOT


class VersionedModel(BaseModel):
    """Base model with schema versioning."""

    version: int = 1


class ArtifactMetadata(VersionedModel):
    """Metadata shared by all artifacts."""

    recording_id: str

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Artifact(VersionedModel, ABC):
    """
    Base class for persisted artifacts.

    Handles locating the recording workspace.
    Subclasses only define their own location inside it.
    """

    metadata: ArtifactMetadata

    def workspace_path(self) -> Path:
        """
        Root directory for this recording.

        Example:
            ~/.dossier/recordings/rec_001/
        """
        return STORAGE_ROOT / "recordings" / self.metadata.recording_id

    @abstractmethod
    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        pass
