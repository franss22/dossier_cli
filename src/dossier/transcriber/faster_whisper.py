"""Faster Whisper transcriber."""

from __future__ import annotations

import statistics
from time import perf_counter, process_time
from typing import TYPE_CHECKING, Any

import faster_whisper
from faster_whisper import WhisperModel
from icecream import ic

from dossier.artifact.transcripts import (
    ChunkTranscriptArtifact,
    TranscriptSegment,
)
from dossier.artifact.transcripts.chunk import (
    ChunkDebugInfo,
    ChunkSource,
    ChunkTranscriptMetrics,
)
from dossier.artifact.transcripts.segment import (
    RawDecoderOutput,
    TranscriptWord,
)
from dossier.transcriber.transcriber import (
    Transcriber,
    TranscriptionProgressCallback,
)
from dossier.utils.ffmpeg import FFMPEG_VERSION
from dossier.utils.serializing import jsonable_object
from dossier.utils.types import _UNSET, _Unset

if TYPE_CHECKING:
    from pathlib import Path

    from faster_whisper.transcribe import Segment, TranscriptionInfo, Word

    from dossier.artifact.chunks import ChunkMetadata

VERSIONS = {
    "faster_whisper": faster_whisper.__version__,
    "ffmpeg": FFMPEG_VERSION,
}


class FasterWhisperTranscriber(Transcriber):
    """Transcriber implementation using Faster-Whisper."""

    model: WhisperModel

    backend_name = "faster_whisper"

    # Current chunk
    _chunk: ChunkMetadata
    _track_id: str

    # Decoder output
    _raw_segments: list[Segment]
    _info: TranscriptionInfo

    # Derived
    _transcript_segments: list[TranscriptSegment]

    # Statistics
    _avg_logprobs: list[float]
    _compression_ratios: list[float]
    _no_speech_probs: list[float]
    _speech_duration: float

    # Timing
    _wall_start: float
    _wall_end: float
    _cpu_start: float
    _cpu_end: float

    @property
    def _wall_time(self) -> float:
        """Total wall-clock time spent processing the chunk."""
        return self._wall_end - self._wall_start

    @property
    def _cpu_time(self) -> float:
        """Total CPU time spent processing the chunk."""
        return self._cpu_end - self._cpu_start

    @property
    def _processing_realtime_factor(self) -> float:
        """Ratio of processing time to audio duration.

        1.0 means realtime processing.
        <1.0 means faster than realtime.
        >1.0 means slower than realtime.
        """
        return self._wall_time / self._chunk.duration

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
        """Transcribe a single audio chunk."""
        self._chunk = chunk
        self._track_id = track_id

        kwargs = self._transcribe_kwargs()
        self._wall_start = perf_counter()
        self._cpu_start = process_time()

        segments, info = self.model.transcribe(str(self.chunkset.resolve(chunk)), **kwargs)
        self._raw_segments = list(segments)  # Consumes the generator,  actual decoding happens here

        self._wall_end = perf_counter()
        self._cpu_end = process_time()
        self._info = info

        transcript_segments = self._build_segments()
        self._transcript_segments = transcript_segments

        return ChunkTranscriptArtifact(
            metadata=self.artifact_metadata,
            track_id=track_id,
            chunk_id=chunk.id,
            chunk_index=chunk.index,
            transcription=self.transcription,
            decoder=self.transcription.decoder.model_copy(
                deep=True,
                update={
                    "configured_options": kwargs,
                    "runtime_options": jsonable_object(
                        info,
                        exclude={
                            "segments",
                            "words",
                            "transcription_options.suppress_tokens",
                            "transcription_options.initial_prompt",
                            "transcription_options.temperatures",
                            "transcription_options.prepend_punctuations",
                            "transcription_options.append_punctuations",
                            "transcription_options.clip_timestamps",
                            "transcription_options.multilingual",
                        },
                    ),
                },
            ),
            source=self._build_chunk_source(),
            metrics=self._build_metrics(),
            diagnostics=self._build_diagnostics(),
            segments=transcript_segments,
        )

    def _transcribe_kwargs(self) -> dict[str, Any]:
        """Build FasterWhisper transcription options."""
        prompt = self.prompt.read_text("utf-8") if self.prompt else None

        return {
            "language": self.language,
            "initial_prompt": prompt,
            "vad_filter": True,
            "vad_parameters": {
                "min_silence_duration_ms": 300,
            },
            "beam_size": 2,
            "condition_on_previous_text": False,
            "hallucination_silence_threshold": 2.0,
            "word_timestamps": True,
        }

    def _build_segments(
        self,
    ) -> list[TranscriptSegment]:
        """Convert FasterWhisper segments into transcript segments."""
        transcript_segments: list[TranscriptSegment] = []

        for segment in self._raw_segments:
            text = segment.text.strip()

            if not text:
                ic("Skipping empty segment")
                continue

            transcript_segments.append(
                TranscriptSegment(
                    start=self._chunk.start + float(segment.start),
                    end=self._chunk.start + float(segment.end),
                    text=text,
                    track_id=self._track_id,
                    chunk_id=self._chunk.id,
                    chunk_index=self._chunk.index,
                    transcription_id=self.transcription.id,
                    raw_decoder_output=RawDecoderOutput(
                        data=jsonable_object(
                            segment,
                            exclude={"words", "tokens"},
                        )
                    ),
                    words=[self._build_word(self._chunk.start, word) for word in (segment.words or [])],
                )
            )

        return transcript_segments

    @staticmethod
    def _build_word(
        chunk_start: float,
        word: Word,
    ) -> TranscriptWord:
        """Convert a FasterWhisper word."""
        return TranscriptWord(
            start=chunk_start + word.start,
            end=chunk_start + word.end,
            word=word.word,
            probability=word.probability,
        )

    def _build_metrics(self) -> ChunkTranscriptMetrics:
        """Compute chunk-level transcription metrics."""
        decoder_outputs = [
            s.raw_decoder_output.data for s in self._transcript_segments if s.raw_decoder_output is not None
        ]

        logprobs = [d["avg_logprob"] for d in decoder_outputs if d.get("avg_logprob") is not None]

        compression = [d["compression_ratio"] for d in decoder_outputs if d.get("compression_ratio") is not None]

        no_speech = [d["no_speech_prob"] for d in decoder_outputs if d.get("no_speech_prob") is not None]

        raw_segment_count = len(self._raw_segments)
        return ChunkTranscriptMetrics(
            raw_segment_count=raw_segment_count,
            kept_segment_count=len(self._transcript_segments),
            discarded_segment_count=raw_segment_count - len(self._transcript_segments),
            transcribed_speech_duration_seconds=sum(segment.duration for segment in self._transcript_segments),
            average_logprob=(statistics.fmean(logprobs) if logprobs else None),
            worst_logprob=(min(logprobs) if logprobs else None),
            max_compression_ratio=(max(compression) if compression else None),
            average_no_speech_probability=(statistics.fmean(no_speech) if no_speech else None),
            cpu_time_seconds=self._cpu_time,
            wall_time_seconds=self._wall_time,
            processing_realtime_factor=self._processing_realtime_factor,
        )

    def _build_diagnostics(self) -> ChunkDebugInfo:
        """Build diagnostic metadata."""
        return ChunkDebugInfo(
            versions=VERSIONS,
            transcription_info=jsonable_object(
                self._info, exclude={"segments", "words", "transcription_options.suppress_tokens"}
            ),
        )

    def _build_chunk_source(
        self,
    ) -> ChunkSource:
        """Build source metadata."""
        return ChunkSource(
            track_id=self._track_id,
            chunk_id=self._chunk.id,
            chunk_index=self._chunk.index,
            start=self._chunk.start,
            end=self._chunk.end,
            duration=self._chunk.end - self._chunk.start,
        )
