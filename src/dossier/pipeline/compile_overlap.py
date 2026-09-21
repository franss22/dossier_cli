"""Functions for handling overlapping chunks in transcription."""

import difflib

from dossier.artifact.transcripts import TranscriptSegment

# These values intentionally bias toward conservative duplicate detection.
# We only merge when both timing overlap and textual similarity are strong,
# so neighboring chunks are less likely to collapse genuinely distinct lines.
SIMILARITY_THRESHOLD = 0.7
MIN_OVERLAP_RATIO = 0.5


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


def _text_similarity(
    a: str,
    b: str,
) -> float:
    """Return a normalized text similarity score."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def _should_merge(
    a: TranscriptSegment,
    b: TranscriptSegment,
) -> bool:
    """Determine whether two overlapping segments likely represent the same utterance."""
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


def _choose_segment(
    a: TranscriptSegment,
    b: TranscriptSegment,
) -> TranscriptSegment:
    """Choose the stronger duplicate candidate using simple length-based heuristics."""
    return max(
        a,
        b,
        key=lambda s: (
            s.end - s.start,
            len(s.text),
        ),
    )


def _stitch_chunks(
    previous: list[TranscriptSegment],
    current: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    """Merge two adjacent chunks while deduplicating overlap candidates near the boundary."""
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


def merge_overlap_track(
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
