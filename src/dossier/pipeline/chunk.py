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
from datetime import UTC, datetime

from rich.progress import Progress

from dossier.artifact.base import ArtifactMetadata
from dossier.artifact.chunks import ChunkMetadata, ChunkSetArtifact, ChunkSetConfiguration, TrackChunkManifest
from dossier.artifact.recording import AudioTrack, RecordingArtifact
from dossier.utils.ffmpeg import segment


def chunk_recording(rec_id: str, chunk_minutes: int, overlap_seconds: int) -> ChunkSetArtifact:
    """Split all tracks of a recording into overlapping chunks."""
    # Define chunking id
    chunking_id = ChunkSetConfiguration.build_id(chunk_minutes, overlap_seconds)
    # Load recording artifact
    rec = RecordingArtifact.load(rec_id)
    chunk_config = ChunkSetConfiguration(
        id=chunking_id,
        duration_seconds=chunk_minutes * 60,
        overlap_seconds=overlap_seconds,
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
        metadata=ArtifactMetadata(recording_id=rec_id, created_at=datetime.now(UTC)),
        chunk_run=chunk_config,
        tracks=chunk_manifests,
    )
    manifest_artifact.save()
    return manifest_artifact


def split_track(
    track: AudioTrack,
    recording: RecordingArtifact,
    chunk_config: ChunkSetConfiguration,
) -> list[ChunkMetadata]:
    """Split an audio track into overlapping WAV chunks."""
    output_dir = recording.workspace_path() / "chunks" / chunk_config.id
    output_dir.mkdir(parents=True, exist_ok=True)

    chunk_seconds = chunk_config.duration_seconds
    step_seconds = chunk_seconds - chunk_config.overlap_seconds

    total_chunks = math.ceil(track.duration / step_seconds)

    chunks: list[ChunkMetadata] = []

    with Progress() as progress:
        task = progress.add_task(
            f"Splitting {track.id} into {chunk_seconds / 60:.2f}min chunks"
            f" with {chunk_config.overlap_seconds}s overlap",
            total=total_chunks,
        )

        for index in range(total_chunks):
            start = index * step_seconds

            if start >= track.duration:
                break

            end = min(start + chunk_seconds, track.duration)

            chunk_id = f"{track.id}/chunk_{index:03d}"
            output = output_dir / f"{chunk_id}.wav"

            segment(
                input_file=recording.workspace_path() / track.file,
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
                    file=output.name,
                )
            )

            progress.advance(task)

    return chunks
