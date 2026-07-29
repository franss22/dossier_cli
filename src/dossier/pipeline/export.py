"""Export transcription artifacts into a complete, final transcript."""

from enum import StrEnum
from pathlib import Path

from dossier.artifact.transcripts.compiled import CompiledTranscriptArtifact


class ExportMode(StrEnum):
    """Export modes for transcripts."""

    LEAN = "lean"
    LLM = "llm"


def export_transcription(transcript: CompiledTranscriptArtifact, mode: ExportMode) -> Path:
    """
    Export a compiled transcript artifact into a final transcript file.

    Args:
        transcript: The compiled transcript artifact to export.
        mode: The export mode (e.g., Gemini, Markdown).

    Returns:
        The path to the exported transcript file.
    """
    match mode:
        case ExportMode.LEAN:
            from dossier.pipeline.exports.lean_json import export_lean_json_transcript

            export = export_lean_json_transcript(transcript)
        case ExportMode.LLM:
            from dossier.pipeline.exports.llm_ready import export_llm_ready_transcript

            export = export_llm_ready_transcript(transcript)
        case _:
            raise ValueError(f"Unsupported transcript export mode: {mode}")

    return export.save()
