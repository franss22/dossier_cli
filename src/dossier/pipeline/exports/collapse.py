"""Utilities for collapsing transcriptiuon segments into a single segment per speaker.

[2169]	8190.67-8191.77	Emi (GM): hay un botón
[2170]	8203.74-8205.28	Taco (Mastiff): anda, me compré una
[2171]	8205.28-8206.2	Taco (Mastiff): libreta para esto
[2172]	8206.2-8220.82	Taco (Mastiff): si la llevo el domingo te la muestro
[2173]	8207.01-8207.53	Menares (Morgan): Vale

Becomes

[2169]	8190.67-8191.77	Emi (GM): hay un botón
[2170]	8203.74-8220.82	Taco (Mastiff): anda, me compré una libreta para esto si la llevo el domingo te la muestro
[2173]	8207.01-8207.53	Menares (Morgan): Vale

"""

from dossier.artifact.transcripts.segment import TranscriptSegment

MAX_GAP_SECONDS = 2.0  # Maximum gap between segments to consider them contiguous


def collapse_segments(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Collapse contiguous segments from the same speaker into a single segment."""
    if not segments:
        return []
    segments = sorted(segments, key=lambda s: s.start)
    collapsed_segments: list[TranscriptSegment] = []
    current_segment = segments[0]

    for next_segment in segments[1:]:
        gap = next_segment.start - current_segment.end
        if next_segment.track_id == current_segment.track_id and gap <= MAX_GAP_SECONDS:
            # Merge segments
            current_segment = collapse_pair(current_segment, next_segment)
        else:
            collapsed_segments.append(current_segment)
            current_segment = next_segment

    collapsed_segments.append(current_segment)
    return collapsed_segments


def collapse_pair(first: TranscriptSegment, second: TranscriptSegment) -> TranscriptSegment:
    """Merge contiguous segments from the same speaker into a single segment, retaining some metadata."""
    if first.track_id != second.track_id:
        raise ValueError("Cannot merge segments from different speakers")

    return TranscriptSegment(
        start=first.start,
        end=second.end,
        text=f"{first.text} {second.text}",
        track_id=first.track_id,
        chunk_id=first.chunk_id,  # Retain the chunk_id of the first segment
        chunk_index=first.chunk_index,  # Retain the chunk_index of the first segment
        transcription_id=first.transcription_id,  # Retain the transcription_id of the first segment
        words=first.words + second.words,  # Concatenate the words from both segments
    )
