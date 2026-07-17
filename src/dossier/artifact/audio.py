"""Audio artifacts for Dossier."""

from pydantic import BaseModel
from pathlib import Path

from dossier.artifact.base import Artifact


class AudioTrack(BaseModel):
    """A normalized audio track."""

    id: str
    file: str
    channels: int = 1


class AudioMetadata(BaseModel):
    """Normalized audio information."""

    duration: float
    sample_rate: int
    tracks: list[AudioTrack]


class AudioArtifact(Artifact):
    """
    Normalized audio metadata.

    Stored as:

        audio.json
    """

    audio: AudioMetadata

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self.workspace_path() / "audio.json"

    @classmethod
    def load(cls, recording_id: str) -> "AudioArtifact":
        """Load an audio artifact from disk."""
        from dossier.storage import load_file

        path = cls.workspace_path_static(recording_id) / "audio.json"

        return load_file(path, cls)
