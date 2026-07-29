"""Audio splitting and chunking artifacts.

- Read/receive recording artifact
- Create folder structure for chunks
- Generate chunks for each track
- Save chunk manifest artifact


chunks/
└── {chunking_id}/
    │
    ├── manifest.json
    │
    ├── track_001/
    │   ├── chunk_000.wav
    │   └── chunk_001.wav
    │
    └── track_002/
        ├── chunk_000.wav
        └── chunk_001.wav
"""

import math

from rich.progress import Progress

from dossier.artifact.base import FileMetadata
from dossier.artifact.chunks import (
    ChunkingMode,
    ChunkMetadata,
    ChunkSetArtifact,
    ChunkSetConfiguration,
    TrackChunkManifest,
)
from dossier.artifact.recording import AudioTrack, RecordingArtifact
from dossier.utils.ffmpeg import segment


def chunk_recording(rec_id: str, chunk_minutes: int, overlap_seconds: int, mode: ChunkingMode) -> ChunkSetArtifact:
    """Split all tracks of a recording into overlapping chunks."""
    if mode == ChunkingMode.SPLIT or mode == ChunkingMode.FULL:
        overlap_seconds = 0
    if mode == ChunkingMode.FULL:
        chunk_minutes = -1
    # Define chunking id
    chunking_id = ChunkSetConfiguration.build_id(chunk_minutes, overlap_seconds, mode)
    # Load recording artifact
    rec = RecordingArtifact.load(rec_id)
    chunk_config = ChunkSetConfiguration(
        id=chunking_id, duration_seconds=chunk_minutes * 60, overlap_seconds=overlap_seconds, mode=mode
    )
    # For each track, split into chunks
    chunk_manifests: list[TrackChunkManifest] = []
    for track in rec.audio.tracks:
        # Get track duration
        # Split track into chunks
        chunks = split_track(
            track=track,
            recording=rec,
            chunk_config=chunk_config,
        )
        # Save chunk manifest artifact for this track
        manifest = TrackChunkManifest(track_id=track.id, chunks=chunks)
        chunk_manifests.append(manifest)

    manifest_artifact = ChunkSetArtifact(
        metadata=FileMetadata.new(recording_id=rec_id),
        chunk_run=chunk_config,
        tracks=chunk_manifests,
    )
    manifest_artifact.save()
    return manifest_artifact


def build_chunk_ranges(
    track: AudioTrack,
    chunk_config: ChunkSetConfiguration,
) -> list[tuple[float, float]]:
    """Build a list of (start, end) tuples for each chunk of a track.

    Modes:
    - FULL: Do not split the audio, just transcribe the full track as one chunk.
    - SPLIT: Split the audio into non-overlapping chunks. (overrides overlap to 0)
    - OVERLAP: Split the audio into overlapping chunks.
    """
    match chunk_config.mode:
        case ChunkingMode.FULL:
            return [(0.0, track.duration)]

        case ChunkingMode.SPLIT:
            chunk_size = chunk_config.duration_seconds
            step = chunk_size

        case ChunkingMode.OVERLAP:
            chunk_size = chunk_config.duration_seconds
            step = chunk_size - chunk_config.overlap_seconds

    ranges: list[tuple[float, float]] = []

    for start in range(0, math.ceil(track.duration), step):
        end = min(start + chunk_size, track.duration)
        ranges.append((float(start), end))

    return ranges


def split_msg(chunk_config: ChunkSetConfiguration, track: AudioTrack) -> str:
    """Build a message describing how the track will be split into chunks."""
    match chunk_config.mode:
        case ChunkingMode.FULL:
            return f"Processing {track.id} as full track"

        case ChunkingMode.SPLIT:
            return f"Splitting {track.id} into {chunk_config.duration_seconds / 60:.2f}min chunks (no overlap)"

        case ChunkingMode.OVERLAP:
            return (
                f"Splitting {track.id} into {chunk_config.duration_seconds / 60:.2f}min"
                f" chunks with {chunk_config.overlap_seconds}s overlap"
            )


def split_track(
    track: AudioTrack,
    recording: RecordingArtifact,
    chunk_config: ChunkSetConfiguration,
) -> list[ChunkMetadata]:
    """Split an audio track according to the configured chunking mode."""
    workspace_root = recording.workspace_path()
    output_dir = workspace_root / "chunks" / chunk_config.id
    output_dir.mkdir(parents=True, exist_ok=True)

    ranges = build_chunk_ranges(track, chunk_config)
    total_chunks = len(ranges)

    chunks: list[ChunkMetadata] = []

    with Progress() as progress:
        task = progress.add_task(split_msg(chunk_config, track), total=total_chunks)

        for index, (start, end) in enumerate(ranges):
            chunk_id = f"{track.id}/chunk_{index:03d}"
            output = output_dir / f"{chunk_id}.wav"

            segment(
                input_file=recording.resolve(track),
                output_file=output,
                start=start,
                end=end,
                sample_rate=track.sample_rate,
                channels=track.channels,
            )

            chunks.append(
                ChunkMetadata(
                    id=ChunkMetadata.build_id(track_id=track.id, index=index),
                    index=index,
                    start=start,
                    end=end,
                    working_path=output.relative_to(workspace_root),
                )
            )

            progress.advance(task)

    return chunks


def build_implicit_chunkset(recording: RecordingArtifact) -> ChunkSetArtifact:
    """Build an implicit chunk set for FULL mode, which just points to the source tracks."""
    chunking_id = ChunkSetConfiguration.build_id(duration_mins=-1, overlap_seconds=0, mode=ChunkingMode.FULL)
    chunk_config = ChunkSetConfiguration(id=chunking_id, duration_seconds=-1, overlap_seconds=0, mode=ChunkingMode.FULL)
    chunk_manifests: list[TrackChunkManifest] = []
    for track in recording.audio.tracks:
        metadata = ChunkMetadata(
            id=ChunkMetadata.build_id(track_id=track.id, index=0),
            index=0,
            start=0.0,
            end=track.duration,
            working_path=track.working_path,
        )
        manifest = TrackChunkManifest(track_id=track.id, chunks=[metadata])
        chunk_manifests.append(manifest)

    manifest_artifact = ChunkSetArtifact(
        metadata=FileMetadata.new(recording_id=recording.metadata.recording_id),
        chunk_run=chunk_config,
        tracks=chunk_manifests,
    )
    return manifest_artifact
