"""wav transcription functions."""

from pathlib import Path

from faster_whisper import WhisperModel

from dossier.utils.dir import REPO_ROOT
from dossier.utils.types import AudioChunk, Segment, TranscribedChunk

PROMPT = REPO_ROOT / "transcription_prompt.md"


class WhisperTranscriber:
    """Transcribes audio using the Whisper model."""

    _model: WhisperModel
    language: str | None
    prompt: Path | None = None

    def __init__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        language: str | None,
        prompt: Path | None = None,
    ) -> None:

        self.language = language
        self.prompt = prompt

        self._model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )

    def transcribe_chunk(
        self,
        chunk: AudioChunk,
    ) -> TranscribedChunk:
        """Transcribe a single audio chunk."""
        prompt_text = self.prompt.read_text() if self.prompt else None
        segments, _info = self._model.transcribe(
            str(chunk.path),
            language=self.language,
            initial_prompt=prompt_text,
        )
        return [
            Segment(
                start=chunk.start_time + float(s.start),
                end=chunk.start_time + float(s.end),
                text=s.text.strip(),
                speaker=None,
            )
            for s in segments
        ]


def build_prompt() -> str:
    """Build a rolling prompt for the transcription model."""
    ...
