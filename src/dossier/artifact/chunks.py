"""Chunk artifacts for audio processing."""

from pydantic import BaseModel

from pathlib import Path
from dossier.artifact.base import Artifact
from dossier.artifact.audio import AudioMetadata


class ChunkTrack(BaseModel):
    """A track inside a chunk."""

    track_id: str
    file: str


class ChunkMetadata(BaseModel):
    """A single audio processing unit."""

    id: str
    index: int

    start: float
    end: float

    tracks: list[ChunkTrack]


class ChunkingConfiguration(BaseModel):
    """Parameters used to create chunks."""

    id: str

    duration_seconds: float
    overlap_seconds: float


class ChunkManifestArtifact(Artifact):
    """
    Audio chunk layout.

    Stored as:

        chunks/manifest.json
    """

    audio: AudioMetadata
    chunking: ChunkingConfiguration
    chunks: list[ChunkMetadata]
    expected_chunks: int

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self.workspace_path() / "chunks" / self.chunking.id / "manifest.json"
