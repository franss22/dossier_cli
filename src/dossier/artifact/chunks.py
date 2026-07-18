"""Chunk artifacts for audio processing."""

from pathlib import Path

from pydantic import BaseModel

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

    @classmethod
    def build_id(cls, track_id: str, index: int) -> str:
        """Build a chunk ID from a track ID and index."""
        return f"{track_id}/{index:03d}"

    def full_path(self, chunking_path: Path, track_id: str) -> Path:
        """Absolute path to the chunk audio file."""
        return chunking_path / track_id / self.path


class TrackChunkManifest(BaseModel):
    """Chunk manifest for one audio track."""

    track_id: str
    chunks: list[ChunkMetadata]


class ChunkSetConfiguration(BaseModel):
    """Parameters used to generate audio chunks."""

    id: str

    duration_seconds: int
    overlap_seconds: int

    @classmethod
    def build_id(cls, duration_mins: int, overlap_seconds: int) -> str:
        """Build a chunking configuration ID from duration and overlap."""
        return f"chunkset_{duration_mins:.0f}min_{overlap_seconds:.0f}s"


class ChunkSetArtifact(Artifact):
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

    chunk_run: ChunkSetConfiguration

    tracks: list[TrackChunkManifest]

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self.workspace_path() / "chunks" / self.chunk_run.id / "manifest.json"

    def chunking_path(self) -> Path:
        """Root directory for this chunking operation."""
        return self.workspace_path() / "chunks" / self.chunk_run.id

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
    def list(cls, recording_id: str) -> list["ChunkSetArtifact"]:
        """List all chunk set artifacts for a given recording."""
        directory = cls.workspace_path_static(recording_id) / "chunks"

        if not directory.exists():
            return []

        return sorted(
            [
                cls.load(recording_id, folder.name)
                for folder in directory.iterdir()
                if folder.is_dir() and (folder / "manifest.json").exists()
            ],
            key=lambda artifact: artifact.chunk_run.id,
        )

    @classmethod
    def load(
        cls,
        recording_id: str,
        chunkset_id: str,
    ) -> "ChunkSetArtifact":
        """Load a chunk manifest artifact from disk."""
        from dossier.utils.storage import load_file

        path = cls.workspace_path_static(recording_id) / "chunks" / chunkset_id / "manifest.json"

        return load_file(path, cls)
