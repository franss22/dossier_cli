"""Merge chunked transcription into a final transcript."""

from dossier.artifact.recording import RecordingArtifact
from dossier.artifact.transcript import (
    MergedTranscriptArtifact,
    TranscriptionRunArtifact,
    TranscriptSegment,
)

SIMILARITY_THRESHOLD = 0.7
MIN_OVERLAP_RATIO = 0.5


def merge_transcription(
    run: TranscriptionRunArtifact,
) -> MergedTranscriptArtifact:
    """
    Merge all chunk transcripts into a final transcript artifact.

    This performs:
    - chunk stitching within each track
    - track interleaving
    - final artifact creation
    """
    merged_tracks: list[list[TranscriptSegment]] = []

    for track in run.tracks:
        chunk_states = run.get_track_chunks(track.id)

        if any(not state.completed for state in chunk_states.values()):
            raise ValueError(f"Cannot merge track {track.id}: not all chunks are completed.")

        chunks = sorted(
            (
                state.load_chunk(
                    recording_id=run.metadata.recording_id,
                    transcription_id=run.transcription.id,
                )
                for state in chunk_states.values()
            ),
            key=lambda chunk: chunk.chunk_index,
        )
        merged_tracks.append(
            _merge_track(
                [chunk.segments for chunk in chunks],
            )
        )

    artifact = MergedTranscriptArtifact(
        metadata=run.metadata,
        tracks=run.tracks,
        transcription=run.transcription,
        segments=_interleave_tracks(merged_tracks),
        recording=RecordingArtifact.load(run.metadata.recording_id).recording,
    )
    artifact.save()

    run.merged = True
    run.save()

    return artifact


def _merge_track(
    chunks: list[list[TranscriptSegment]],
) -> list[TranscriptSegment]:
    """Merge all chunks belonging to a single track."""
    if not chunks:
        return []

    chunks = [
        _trim_chunk(
            chunk,
            is_first=i == 0,
            is_last=i == len(chunks) - 1,
        )
        for i, chunk in enumerate(chunks)
    ]

    merged = chunks[0]

    for chunk in chunks[1:]:
        merged = _stitch_chunks(
            merged,
            chunk,
        )

    return merged


def _trim_chunk(
    segments: list[TranscriptSegment],
    *,
    is_first: bool,
    is_last: bool,
) -> list[TranscriptSegment]:
    """Discard likely cut-off boundary segments."""
    if len(segments) < 3:
        return segments.copy()

    start = 0 if is_first else 1
    end = len(segments) if is_last else -1

    return segments[start:end]


def _stitch_chunks(
    previous: list[TranscriptSegment],
    current: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    """Merge two adjacent chunks."""
    merged = previous.copy()

    for segment in current:
        match = None

        for candidate in reversed(merged):
            if candidate.end < segment.start:
                break

            if _should_merge(candidate, segment):
                match = candidate
                break

        if match is None:
            merged.append(segment)
        else:
            merged[merged.index(match)] = _choose_segment(
                match,
                segment,
            )

    return merged


def _interleave_tracks(
    tracks: list[list[TranscriptSegment]],
) -> list[TranscriptSegment]:
    """Combine multiple tracks into chronological order."""
    return sorted(
        (segment for track in tracks for segment in track),
        key=lambda s: (s.start, s.end, s.track_id),
    )


def _should_merge(
    a: TranscriptSegment,
    b: TranscriptSegment,
) -> bool:
    """Determine whether two segments are duplicates."""
    overlap = min(a.end, b.end) - max(a.start, b.start)

    if overlap <= 0:
        return False

    overlap_ratio = overlap / min(
        a.end - a.start,
        b.end - b.start,
    )

    if overlap_ratio < MIN_OVERLAP_RATIO:
        return False

    return _text_similarity(a.text, b.text) >= SIMILARITY_THRESHOLD


def _text_similarity(
    a: str,
    b: str,
) -> float:
    """Return a normalized text similarity score."""
    import difflib

    return difflib.SequenceMatcher(None, a, b).ratio()


def _choose_segment(
    a: TranscriptSegment,
    b: TranscriptSegment,
) -> TranscriptSegment:
    """Choose the higher-quality duplicate."""
    return max(
        a,
        b,
        key=lambda s: (
            s.end - s.start,
            len(s.text),
        ),
    )
