"""Compile chunked transcription into a final transcript."""

from dossier.artifact.chunks import ChunkingMode
from dossier.artifact.recording import RecordingArtifact
from dossier.artifact.transcripts import (
    CompiledTranscriptArtifact,
    TranscriptionRunArtifact,
    TranscriptSegment,
)
from dossier.pipeline.compile_overlap import merge_overlap_track


def compile_transcription(
    run: TranscriptionRunArtifact,
) -> CompiledTranscriptArtifact:
    """
    Compile all chunk transcripts into a final transcript artifact.

    This performs:
    - chunk stitching within each track
    - track interleaving
    - final artifact creation
    """
    compile_tracks = _compile_tracks_for_mode(run)

    artifact = CompiledTranscriptArtifact(
        metadata=run.metadata.fresh(),
        tracks=run.tracks,
        transcription=run.transcription,
        segments=_interleave_tracks(compile_tracks),
        recording=RecordingArtifact.load(run.metadata.recording_id).recording,
    )
    artifact.save()

    run.compiled = True
    run.save()

    return artifact


def compile_full(run: TranscriptionRunArtifact) -> list[list[TranscriptSegment]]:
    """Compile a full-track transcription (1 chunk per track) run into a final transcript artifact."""
    compiled_tracks: list[list[TranscriptSegment]] = []

    for track in run.tracks:
        chunks = run.load_track_chunks(track.id)
        if len(chunks) != 1:
            raise ValueError(f"Cannot compile full-track transcription: track {track.id} does not have exactly chunk.")
        compiled_tracks.append(chunks[0].segments)

    return compiled_tracks


def compile_split(run: TranscriptionRunArtifact) -> list[list[TranscriptSegment]]:
    """Compile a split-chunk transcription run into a final transcript artifact."""
    compiled_tracks: list[list[TranscriptSegment]] = []
    for track in run.tracks:
        chunks = run.load_track_chunks(track.id)
        compiled_tracks.append([segment for chunk in chunks for segment in chunk.segments])
    return compiled_tracks


def compile_overlap(run: TranscriptionRunArtifact) -> list[list[TranscriptSegment]]:
    """Compile an overlapping-chunk transcription run into a final transcript artifact."""
    merged_tracks: list[list[TranscriptSegment]] = []

    for track in run.tracks:
        chunks = run.load_track_chunks(track.id)
        merged_tracks.append(merge_overlap_track([chunk.segments for chunk in chunks]))

    return merged_tracks


def _compile_tracks_for_mode(run: TranscriptionRunArtifact) -> list[list[TranscriptSegment]]:
    """Compile track transcript segments using the run's chunking mode."""
    mode = run.chunk_configuration.mode
    if mode.is_full_track():
        return compile_full(run)
    if mode.uses_overlap_merge():
        return compile_overlap(run)
    return compile_split(run)


def _interleave_tracks(
    tracks: list[list[TranscriptSegment]],
) -> list[TranscriptSegment]:
    """Combine multiple tracks into chronological order."""
    return sorted(
        (segment for track in tracks for segment in track),
        key=lambda s: (s.start, s.end, s.track_id),
    )
