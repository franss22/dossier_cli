"""Export transcription artifacts into Lean JSON format."""

from pathlib import Path

from pydantic import BaseModel

from dossier.artifact.base import Export, JsonFile
from dossier.artifact.transcripts.compiled import CompiledTranscriptArtifact
from dossier.pipeline.exports.collapse import collapse_segments
from dossier.utils.timestamp import timestamp


class LeanSegment(BaseModel):
    """A single segment in the Lean JSON transcript format."""

    id: int
    start_time: float
    end_time: float
    duration: float
    text: str
    speaker_id: str


class LeanJsonTranscript(Export, JsonFile):
    """A Lean JSON transcript containing multiple segments."""

    segments: list[LeanSegment]

    @classmethod
    def _path(cls, recording_id: str) -> Path:
        """Return the storage path for this export."""
        return cls.export_path_static(recording_id) / f"lean_json_transcript_{timestamp()}.json"


def export_lean_json_transcript(transcript: CompiledTranscriptArtifact) -> LeanJsonTranscript:
    """
    Export a compiled transcript artifact into Lean JSON format.

    Args:
        transcript: The compiled transcript artifact to export.

    Returns:
        The Lean JSON-formatted transcript as a LeanJsonTranscript object.
    """
    collapsed_segments = collapse_segments(transcript.segments)

    segments = [
        LeanSegment(
            id=i,
            start_time=segment.start,
            end_time=segment.end,
            duration=segment.duration,
            text=segment.text,
            speaker_id=segment.track_id,
        )
        for i, segment in enumerate(collapsed_segments)
    ]

    return LeanJsonTranscript(metadata=transcript.metadata.fresh(), segments=segments)
