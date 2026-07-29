"""Generate quick id collapse groupings via heuristics."""

from pydantic import BaseModel

from dossier.artifact.transcripts.segment import TranscriptSegment

MAX_GAP_SECONDS = 1.5  # seconds
MAX_GROUP_DURATION = 20  # seconds


class Group(BaseModel):
    """A group of contiguous segments."""

    start_id: int
    start: float
    end: float
    segment_ids: list[int]

    def __init__(self, segment: TranscriptSegment, index: int) -> None:
        super().__init__(
            start_id=index,
            start=segment.start,
            end=segment.end,
            segment_ids=[index],
        )

    def add_segment(self, segment: TranscriptSegment, index: int) -> None:
        """Add a segment to the group."""
        self.end = segment.end
        self.segment_ids.append(index)


def collapse_segments(segments: list[TranscriptSegment]) -> list[dict]:
    """Collapse contiguous segments into a single segment."""
    if not segments:
        return []
    segments = sorted(segments, key=lambda s: s.start)
    collapsed_segments: list[Group] = []
    current = Group(segments[0], 0)

    for i, next_segment in enumerate(segments[1:], start=1):
        gap = next_segment.start - current.end
        if gap <= MAX_GAP_SECONDS and (next_segment.end - current.start) <= MAX_GROUP_DURATION:
            # Merge segments
            current.add_segment(next_segment, i)
        else:
            collapsed_segments.append(current)
            current = Group(next_segment, i)

    collapsed_segments.append(current)
    return [group.model_dump() for group in collapsed_segments]
