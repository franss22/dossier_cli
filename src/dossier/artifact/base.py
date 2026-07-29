"""Base classes for artifacts.

Artifacts are persisted objects that represent the state of a recording at a given point in time.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Protocol, TypeVar

from pydantic import BaseModel, Field

from dossier.utils.dir import RECORDINGS_DIR
from dossier.utils.timestamp import timestamp


class VersionedModel(BaseModel):
    """Base model with schema versioning."""

    version: int = 1


T = TypeVar("T", bound="Artifact")


class FileMetadata(VersionedModel):
    """Metadata shared by all artifacts."""

    recording_id: str

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    edited_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def new(
        cls,
        recording_id: str,
    ) -> "FileMetadata":
        """Create a new metadata instance with the current timestamp."""
        return FileMetadata(
            recording_id=recording_id,
            created_at=datetime.now(UTC),
            edited_at=datetime.now(UTC),
        )

    def fresh(self) -> "FileMetadata":
        """Create a new metadata instance with the current timestamp."""
        return FileMetadata(
            recording_id=self.recording_id,
            created_at=datetime.now(UTC),
            edited_at=datetime.now(UTC),
        )

    def update_datetime(self) -> "FileMetadata":
        """Update the edited timestamp to the current time."""
        self.edited_at = datetime.now(UTC)
        return self


class StoredFile(BaseModel, ABC):
    """Base class for stored files."""

    metadata: FileMetadata
    file_extension: ClassVar[str] = "json"

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

    @classmethod
    @abstractmethod
    def _path(cls, *args: Any, **kwargs: Any) -> Path:
        """Exact storage location for a file of this class."""
        pass

    @abstractmethod
    def storage_path(self) -> Path:
        """Exact storage location for this instance."""
        pass

    def save(self) -> Path:
        """Encode and save this file to disk."""
        self.metadata.update_datetime()

        path = self.storage_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_bytes(self.encode())
        return path

    @abstractmethod
    def encode(self) -> bytes:
        """Encode this file as bytes."""
        pass


class JsonFile(StoredFile):
    """Base class for JSON files."""

    def encode(self) -> bytes:
        """Encode this file as bytes."""
        return self.model_dump_json(indent=2).encode("utf-8")


class HasWorkingPath(Protocol):
    """Protocol for objects that have a working path."""

    working_path: Path


class Artifact(VersionedModel, JsonFile, ABC):
    """
    Base class for persisted artifacts.

    Handles locating the recording workspace.
    Subclasses only define their own location inside it.

    Subclasses must implement the `storage_path` method to specify their storage location.
    All artifacts include a `metadata` field that contains the recording ID and creation timestamp.
    """

    @classmethod
    def load(cls: type[T], *args: Any, **kwargs: Any) -> T:
        """Load an artifact from disk."""
        from dossier.utils.storage import load_file

        return load_file(cls._path(*args, **kwargs), cls)

    def resolve(self, path: str | Path | HasWorkingPath) -> Path:
        """Resolve a workspace-relative path."""
        if isinstance(path, (str, Path)):
            return self.workspace_path() / path

        return self.workspace_path() / path.working_path

    @classmethod
    def resolve_static(cls, recording_id: str, path: str | Path | HasWorkingPath) -> Path:
        """Resolve a workspace-relative path from a recording ID."""
        if isinstance(path, (str, Path)):
            return cls.workspace_path_static(recording_id) / path

        return cls.workspace_path_static(recording_id) / path.working_path


class Export(StoredFile, ABC):
    """
    Base class for export files.

    Exports are persisted objects that represent a specific export of a recording.
    They are stored in the `exports` directory of the recording workspace.
    """

    @classmethod
    def export_path_static(cls, recording_id: str) -> Path:
        """Root directory for exports."""
        return cls.workspace_path_static(recording_id) / "exports"

    def export_path(self) -> Path:
        """Root directory for exports."""
        return self.export_path_static(self.metadata.recording_id)

    def storage_path(self) -> Path:
        """Exact storage location."""
        return self._path(self.metadata.recording_id)

    @classmethod
    def _path(cls, recording_id: str) -> Path:
        """Exact storage location for a file of this class."""
        return cls.export_path_static(recording_id) / f"{cls.__name__}_{timestamp()}.{cls.file_extension}"
