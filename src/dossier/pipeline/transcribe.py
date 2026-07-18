"""Transcribe audio recordings into text."""

from pathlib import Path

from dossier.artifact.chunks import ChunkSetArtifact
from dossier.artifact.transcripts import TranscriptionRunArtifact
from dossier.ui import transcription_progress_bar
from dossier.utils.types import _UNSET, _Unset


def transcribe_recording(
    rec_id: str,
    model: str,
    device: str,
    compute_type: str,
    chunkset: str,
    language: str | None = None,
    prompt: Path | None | _Unset = _UNSET,
) -> TranscriptionRunArtifact:
    """
    Transcribe a recording into text.

    Args:
        rec_id: The ID of the recording to transcribe.
    """
    from dossier.transcriber.faster_whisper import FasterWhisperTranscriber as Transcriber

    with transcription_progress_bar() as progress_callback:
        transcriber = Transcriber(
            model=model,
            device=device,
            compute_type=compute_type,
            progress_callback=progress_callback,
            recording_id=rec_id,
            language=language,
            prompt=prompt,
        )
        chunks = ChunkSetArtifact.load(rec_id, chunkset)

        return transcriber.transcribe_chunk_set(chunks)
