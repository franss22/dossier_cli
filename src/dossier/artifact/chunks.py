"""Chunk artifacts for audio processing."""

import math
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

    def is_full_track(self) -> bool:
        """Return whether this mode keeps one full-track chunk per track."""
        return self is ChunkingMode.FULL

    def uses_overlap_merge(self) -> bool:
        """Return whether this mode requires overlap-aware compilation."""
        return self is ChunkingMode.OVERLAP

    def normalized_overlap_seconds(self, overlap_seconds: int) -> int:
        """Normalize overlap settings for modes that do not use overlap."""
        return 0 if self is ChunkingMode.SPLIT else overlap_seconds


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
    def create(cls, duration_minutes: int, overlap_seconds: int, mode: ChunkingMode) -> "ChunkSetConfiguration":
        """Build a normalized chunk-set configuration from CLI/config inputs."""
        normalized_overlap_seconds = mode.normalized_overlap_seconds(overlap_seconds)
        duration_seconds = -1 if mode.is_full_track() else duration_minutes * 60
        return cls(
            id=cls.build_id(duration_minutes, normalized_overlap_seconds, mode),
            duration_seconds=duration_seconds,
            overlap_seconds=normalized_overlap_seconds,
            mode=mode,
        )

    @classmethod
    def full(cls) -> "ChunkSetConfiguration":
        """Return the implicit full-track chunk-set configuration."""
        return cls.create(duration_minutes=-1, overlap_seconds=0, mode=ChunkingMode.FULL)

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

    def chunk_ranges(self, duration_seconds: float) -> list[tuple[float, float]]:
        """Return chunk ranges for a track duration using this configuration."""
        if self.mode.is_full_track():
            return [(0.0, duration_seconds)]

        chunk_size = self.duration_seconds
        step = chunk_size - self.overlap_seconds if self.mode.uses_overlap_merge() else chunk_size

        ranges: list[tuple[float, float]] = []
        for start in range(0, math.ceil(duration_seconds), step):
            end = min(start + chunk_size, duration_seconds)
            ranges.append((float(start), end))

        return ranges

    def describe_track(self, track_id: str) -> str:
        """Describe how this configuration will process one track."""
        match self.mode:
            case ChunkingMode.FULL:
                return f"Processing {track_id} as full track"
            case ChunkingMode.SPLIT:
                return f"Splitting {track_id} into {self.duration_seconds / 60:.2f}min chunks (no overlap)"
            case ChunkingMode.OVERLAP:
                return (
                    f"Splitting {track_id} into {self.duration_seconds / 60:.2f}min"
                    f" chunks with {self.overlap_seconds}s overlap"
                )


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
