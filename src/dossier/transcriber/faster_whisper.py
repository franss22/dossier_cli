"""Faster Whisper transcriber."""

from pathlib import Path

from faster_whisper import WhisperModel

from dossier.artifact.chunks import ChunkMetadata
from dossier.artifact.transcript import (
    ChunkTranscriptArtifact,
    TranscriptSegment,
)
from dossier.transcriber.transcriber import (
    Transcriber,
    TranscriptionProgressCallback,
)
from dossier.utils.types import _UNSET, _Unset


class FasterWhisperTranscriber(Transcriber):
    """Transcriber implementation using the Faster Whisper model."""

    model: WhisperModel

    def __init__(
        self,
        *,
        recording_id: str,
        model: str,
        device: str,
        compute_type: str,
        language: str | None = None,
        prompt: Path | None | _Unset = _UNSET,
        progress_callback: TranscriptionProgressCallback | None = None,
    ) -> None:
        self.model = WhisperModel(
            model,
            device=device,
            compute_type=compute_type,
        )

        super().__init__(
            recording_id=recording_id,
            model=model,
            device=device,
            compute_type=compute_type,
            language=language,
            prompt=prompt,
            progress_callback=progress_callback,
        )

    def transcribe_chunk(
        self,
        chunk: ChunkMetadata,
        track_id: str,
    ) -> ChunkTranscriptArtifact:
        """
        Transcribe a single audio chunk.

        Whisper timestamps are relative to the chunk.
        Convert them back into recording timestamps.
        """
        prompt_text = self.prompt.read_text(encoding="utf-8") if self.prompt else None

        segments, _info = self.model.transcribe(
            str(chunk.full_path(self.chunkset.chunking_path(), track_id)),
            language=self.language,
            initial_prompt=prompt_text,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            beam_size=3,
            condition_on_previous_text=False,
            hallucination_silence_threshold=1.0,
        )

        print(_info)

        transcript_segments: list[TranscriptSegment] = []

        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue

            transcript_segments.append(
                TranscriptSegment(
                    start=chunk.start + float(segment.start),
                    end=chunk.start + float(segment.end),
                    text=text,
                    track_id=track_id,
                    chunk_id=chunk.id,
                    chunk_index=chunk.index,
                    transcription_id=self.transcription.id,
                )
            )

        return ChunkTranscriptArtifact(
            metadata=self.artifact_metadata,
            track_id=track_id,
            chunk_id=chunk.id,
            chunk_index=chunk.index,
            transcription=self.transcription,
            segments=transcript_segments,
        )
