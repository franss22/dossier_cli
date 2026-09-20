"""Shared helpers for transcript export transformations."""

from collections.abc import Callable
from typing import TypeVar

from dossier.artifact.transcripts.compiled import CompiledTranscriptArtifact
from dossier.pipeline.exports.collapse import collapse_segments

SegmentT = TypeVar("SegmentT")


def collapsed_segments(transcript: CompiledTranscriptArtifact):
    """Return collapsed transcript segments for export mapping."""
    return collapse_segments(transcript.segments)


def map_collapsed_segments(
    transcript: CompiledTranscriptArtifact,
    builder: Callable[[int, object], SegmentT],
) -> list[SegmentT]:
    """Map collapsed transcript segments into an export-specific representation."""
    return [builder(index, segment) for index, segment in enumerate(collapsed_segments(transcript))]
