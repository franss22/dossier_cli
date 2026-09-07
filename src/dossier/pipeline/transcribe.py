"""Transcribe audio recordings into text."""

from collections.abc import Callable
from pathlib import Path

from dossier.artifact.chunks import ChunkSetArtifact
from dossier.artifact.transcripts import TranscriptionRunArtifact
from dossier.transcriber.transcriber import TranscriptionProgress
from dossier.ui.progress import transcription_progress_bar
from dossier.utils.types import _UNSET, _Unset


def transcribe_recording(
    rec_id: str,
    model: str,
    device: str,
    compute_type: str,
    chunkset: str,
    language: str | None = None,
    prompt: Path | None | _Unset = _UNSET,
    progress_callback: Callable[[TranscriptionProgress], None] | None = None,
) -> TranscriptionRunArtifact:
    """
    Transcribe a recording into text.

    Args:
        rec_id: The ID of the recording to transcribe.
    """
    from dossier.transcriber.faster_whisper import FasterWhisperTranscriber as Transcriber

    if progress_callback is None:
        with transcription_progress_bar() as default_progress_callback:
            transcriber = Transcriber(
                model=model,
                device=device,
                compute_type=compute_type,
                progress_callback=default_progress_callback,
                recording_id=rec_id,
                language=language,
                prompt=prompt,
            )
            chunks = ChunkSetArtifact.load(rec_id, chunkset)

            return transcriber.transcribe_chunk_set(chunks)

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
