"""wav transcription functions."""

from faster_whisper import WhisperModel

from dossier.audio import AudioChunk


from dataclasses import dataclass


@dataclass(slots=True)
class Segment:
    """Represents a segment of transcribed audio.

    ```
    0.00 → 4.82   "Welcome back..."
    4.82 → 9.15   "Last session..."
    9.15 → 13.01  "You entered the hotel..."
    ```
    """

    start: float
    end: float
    text: str
    speaker: str | None


class WhisperTranscriber:
    """Transcribes audio using the Whisper model."""

    _model: WhisperModel
    language: str | None

    def __init__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        language: str | None,
    ) -> None:
        self.language = language

        self._model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )

    def transcribe_chunk(
        self,
        chunk: AudioChunk,
        initial_prompt: str | None = None,
    ) -> list[Segment]:
        """Transcribe a single audio chunk."""
        segments, _info = self._model.transcribe(
            str(chunk.path),
            language=self.language,
            # initial_prompt=initial_prompt,
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
