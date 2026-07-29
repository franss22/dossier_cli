"""Chunk artifacts for audio processing."""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from dossier.artifact.base import Artifact


class ChunkingMode(StrEnum):
    """Modes of splitting an audio into chunks."""

    FULL = "full"
    """Do not split the audio, just transcribe the full track as one chunk."""
    SPLIT = "split"
    """Split the audio into non-overlapping chunks. (overrides overlap to 0)"""
    OVERLAP = "overlap"
    """Split the audio into overlapping chunks."""


class ChunkMetadata(BaseModel):
    """A single chunk belonging to one audio track."""

    id: str
    index: int

    start: float
    end: float

    working_path: Path
    """Audio file path relative to the recording workspace root."""

    @property
    def duration(self) -> float:
        """Duration of the chunk in seconds."""
        return self.end - self.start

    @classmethod
    def build_id(cls, track_id: str, index: int) -> str:
        """Build a chunk ID from a track ID and index."""
        return f"{track_id}/{index:03d}"


class TrackChunkManifest(BaseModel):
    """Chunk manifest for one audio track."""

    track_id: str
    chunks: list[ChunkMetadata]


class ChunkSetConfiguration(BaseModel):
    """Parameters used to generate audio chunks."""

    id: str

    duration_seconds: int
    overlap_seconds: int

    mode: ChunkingMode

    @classmethod
    def build_id(cls, duration_mins: int, overlap_seconds: int, mode: ChunkingMode) -> str:
        """Build a chunking configuration ID from duration and overlap."""
        match mode:
            case ChunkingMode.FULL:
                return "chunkset_full"
            case ChunkingMode.SPLIT:
                return f"chunkset_split_{duration_mins:.0f}min"
            case ChunkingMode.OVERLAP:
                return f"chunkset_overlap_{duration_mins:.0f}min_{overlap_seconds:.0f}s"


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

    @property
    def mode(self) -> ChunkingMode:
        """Chunking mode used to generate this chunk set."""
        return self.chunk_run.mode

    @classmethod
    def _path(cls, recording_id: str, chunk_run_id: str) -> Path:
        return cls.resolve_static(recording_id, f"chunks/{chunk_run_id}/manifest.json")

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return self._path(self.metadata.recording_id, self.chunk_run.id)

    @classmethod
    def list(cls, recording_id: str) -> list["ChunkSetArtifact"]:
        """List all chunk set artifacts for a given recording."""
        directory = cls.resolve_static(recording_id, "chunks")

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
        return super().load(recording_id, chunkset_id)
