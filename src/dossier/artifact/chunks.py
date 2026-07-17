"""Chunk artifacts for audio processing."""

from pathlib import Path

from pydantic import BaseModel

from dossier.artifact.audio import AudioMetadata
from dossier.artifact.base import Artifact


class ChunkMetadata(BaseModel):
    """A single chunk belonging to one audio track."""

    id: str
    index: int

    start: float
    end: float

    file: str

    @property
    def path(self) -> Path:
        """Relative path to the chunk audio file."""
        return Path(self.file)


class TrackChunkManifest(BaseModel):
    """Chunk manifest for one audio track."""

    track_id: str
    chunks: list[ChunkMetadata]


class ChunkingConfiguration(BaseModel):
    """Parameters used to generate audio chunks."""

    id: str

    duration_seconds: float
    overlap_seconds: float


class ChunkManifestArtifact(Artifact):
    """
    Manifest describing all chunks generated for a recording.

    Stored as:

        chunks/{chunking_id}/manifest.json

    Chunk audio is stored by track:

        chunks/{chunking_id}/track_001/chunk_000.wav
        chunks/{chunking_id}/track_001/chunk_001.wav
        ...

        chunks/{chunking_id}/track_002/chunk_000.wav
        chunks/{chunking_id}/track_002/chunk_001.wav
        ...
    """

    audio: AudioMetadata
    chunking: ChunkingConfiguration

    tracks: list[TrackChunkManifest]

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self.workspace_path() / "chunks" / self.chunking.id / "manifest.json"

    def chunking_path(self) -> Path:
        """Root directory for this chunking operation."""
        return self.workspace_path() / "chunks" / self.chunking.id

    def track_directory(self, track_id: str) -> Path:
        """Directory containing all chunks for one track."""
        return self.chunking_path() / track_id

    def chunk_path(
        self,
        track_id: str,
        chunk_id: str,
    ) -> Path:
        """Absolute path to a chunk audio file."""
        return self.track_directory(track_id) / f"{chunk_id}.wav"

    def chunk_relative_path(
        self,
        track_id: str,
        chunk_id: str,
    ) -> Path:
        """Chunk path relative to the chunking directory."""
        return self.chunk_path(track_id, chunk_id).relative_to(self.chunking_path())

    def chunk_relative_file(
        self,
        track_id: str,
        chunk_id: str,
    ) -> str:
        """Portable manifest path for a chunk."""
        return self.chunk_relative_path(track_id, chunk_id).as_posix()

    @classmethod
    def load(
        cls,
        recording_id: str,
        chunking_id: str,
    ) -> "ChunkManifestArtifact":
        """Load a chunk manifest artifact from disk."""
        from dossier.storage import load_file

        path = cls.workspace_path_static(recording_id) / "chunks" / chunking_id / "manifest.json"

        return load_file(path, cls)
