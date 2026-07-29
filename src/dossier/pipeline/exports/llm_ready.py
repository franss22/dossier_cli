"""Export transcription artifacts into LLM-ready format."""

from pydantic import BaseModel

from dossier.artifact.base import Export
from dossier.artifact.transcripts.compiled import CompiledTranscriptArtifact
from dossier.pipeline.exports.collapse import collapse_segments
from dossier.utils.speakers import labelize_tracks


class LLMHeader(BaseModel):
    """Header for LLM-ready transcript format."""

    n_of_segments: int
    speakers: dict[str, str]  # speaker_id -> speaker_name


class LLMSegment(BaseModel):
    """A single segment in the LLM-ready transcript format."""

    id: int
    start_time: float
    end_time: float
    text: str
    speaker: str


class LLMReadyExport(Export):
    """LLM-ready transcript export format."""

    file_extension = "md"

    header: LLMHeader
    segments: list[LLMSegment]

    def encode(self) -> bytes:
        """Encode the export as bytes.

        Uses custom encoding to ensure compatibility with LLMs.

        ```
        # Transcript:
        [<segment_id>]<tab><start_time><tab><speaker_id>: <text>
        ```
        """
        encoded = "# Transcript:\n"
        for segment in self.segments:
            encoded += f"[{segment.id}]\t{segment.start_time:.1f}\t{segment.speaker}: {segment.text}\n"
        return encoded.encode("utf-8")


def export_llm_ready_transcript(transcript: CompiledTranscriptArtifact) -> LLMReadyExport:
    """
    Export a compiled transcript artifact into LLM-ready format.

    Args:
        transcript: The compiled transcript artifact to export.

    Returns:
        The LLM-ready transcript as an LLMReadyExport object.
    """
    speakers = labelize_tracks([track.id for track in transcript.tracks])
    header = LLMHeader(
        n_of_segments=len(transcript.segments),
        speakers=speakers,
    )
    collapsed_segments = collapse_segments(transcript.segments)

    segments = [
        LLMSegment(
            id=id,
            start_time=segment.start_time,
            end_time=segment.end_time,
            text=segment.text,
            speaker=speakers[segment.track_id],
        )
        for id, segment in enumerate(collapsed_segments)
    ]
    return LLMReadyExport(header=header, segments=segments, metadata=transcript.metadata.fresh())
