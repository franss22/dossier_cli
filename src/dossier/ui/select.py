"""UI helpers for selecting artifacts."""

import questionary

from dossier.artifact.chunks import ChunkSetArtifact
from dossier.artifact.transcripts.compiled import CompiledTranscriptArtifact


def select_transcript(transcripts: list[CompiledTranscriptArtifact]) -> CompiledTranscriptArtifact:
    """Prompt the user to select a transcript."""
    if len(transcripts) == 1:
        return transcripts[0]

    choices = [
        questionary.Choice(
            title=f"{transcript.transcription.id} ({transcript.transcription.decoder.model})",
            value=transcript,
        )
        for transcript in transcripts
    ]
    transcript = questionary.select(
        "Select transcript:",
        choices=choices,
    ).ask()
    if transcript is None:
        raise RuntimeError("No transcript selected.")

    return transcript


def _chunkset_repr(chunkset: ChunkSetArtifact) -> str:
    match chunkset.chunk_run.mode:
        case "full":
            return f"{chunkset.chunk_run.id} (full tracks)"
        case "split":
            return f"{chunkset.chunk_run.id} ({chunkset.chunk_run.duration_seconds}s chunks)"
        case "overlap":
            return (
                f"{chunkset.chunk_run.id} "
                f"({chunkset.chunk_run.duration_seconds}s chunks, "
                f"{chunkset.chunk_run.overlap_seconds}s overlap)"
            )
        case _:
            raise ValueError(f"Unknown chunking mode: {chunkset.chunk_run.mode}")


def select_chunkset(chunksets: list[ChunkSetArtifact]) -> ChunkSetArtifact:
    """Prompt the user to select a chunk set."""
    if len(chunksets) == 1:
        return chunksets[0]

    choices = [
        questionary.Choice(
            title=(_chunkset_repr(chunkset)),
            value=chunkset,
        )
        for chunkset in chunksets
    ]
    chunk = questionary.select(
        "Select chunk set:",
        choices=choices,
    ).ask()
    if chunk is None:
        raise RuntimeError("No chunk set selected.")

    return chunk
