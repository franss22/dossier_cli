"""Base classes for artifacts.

Artifacts are persisted objects that represent the state of a recording at a given point in time.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from pathlib import Path

from dossier.utils.dir import RECORDINGS_DIR


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

    Subclasses must implement the `storage_path` method to specify their storage location.
    All artifacts include a `metadata` field that contains the recording ID and creation timestamp.
    """

    metadata: ArtifactMetadata

    @classmethod
    def workspace_path_static(cls, recording_id: str) -> Path:
        """
        Root directory for a recording workspace.

        Example:
            ~/.dossier/recordings/rec_001/
        """
        return RECORDINGS_DIR / recording_id

    def workspace_path(self) -> Path:
        """
        Root directory for this recording.

        Example:
            ~/.dossier/recordings/rec_001/
        """
        return self.workspace_path_static(self.metadata.recording_id)

    @abstractmethod
    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        pass

    @classmethod
    @abstractmethod
    def load(cls, recording_id: str, *args: Any, **kwargs: Any) -> "Artifact":
        """Load an artifact from disk."""
        pass
