"""Mock transcriber for testing transcription pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dossier.artifact.transcript import (
    ChunkTranscriptArtifact,
    TranscriptionRunArtifact,
    TranscriptSegment,
)
from dossier.transcriber.transcriber import Transcriber, TranscriptionProgressCallback
from dossier.utils.types import _UNSET, _Unset

if TYPE_CHECKING:
    from pathlib import Path

    from dossier.artifact.chunks import ChunkMetadata, TrackChunkManifest

PHRASES = [
    ">quick brown fox!!!<",
    ">old manor whispers<",
    ">strange lights fly<",
    ">ancient ruin await<",
    ">monster moves near<",
    ">we open red doors!<",
    ">hidden clue reveal<",
    ">final path begins!<",
    ">cold wind cross!!!<",
    ">dark cave hide now<",
]


@dataclass(frozen=True)
class MockSegment:
    """A mock transcript segment."""

    start: float
    end: float
    text: str


class MockRecording:
    """A mock recording for testing transcription pipelines."""

    phrase_offset: int = 0
    time_offset: float = 0.0
    segment_duration: float = 10.0
    pause_duration: float = 1.0

    def __init__(
        self,
        *,
        phrase_offset: int = 0,
        time_offset: float = 0.0,
        segment_duration: float = 10.0,
        pause_duration: float = 1.0,
    ) -> None:
        self.phrase_offset = phrase_offset
        self.time_offset = time_offset
        self.segment_duration = segment_duration
        self.pause_duration = pause_duration

    def window(
        self,
        start: float,
        end: float,
    ) -> list[MockSegment]:
        """Get the transcript segments that overlap a given time window."""
        interval = self.segment_duration + self.pause_duration

        first_segment = int(start // interval)
        last_segment = int(end // interval)

        segments = []

        for index in range(first_segment, last_segment + 1):
            segment_start = index * interval + self.time_offset
            segment_end = segment_start + self.segment_duration

            if segment_end <= start:
                continue

            if segment_start >= end:
                continue

            segments.append(
                MockSegment(
                    start=segment_start,
                    end=segment_end,
                    text=clip_text(
                        PHRASES[(index + self.phrase_offset) % len(PHRASES)],
                        segment_start=segment_start,
                        segment_end=segment_end,
                        window_start=start,
                        window_end=end,
                    ),
                )
            )

        return segments


class MockTranscriber(Transcriber):
    """Mock transcriber for testing transcription pipelines."""

    recording: MockRecording

    def __init__(
        self,
        *,
        recording_id: str,
        language: str | None = None,
        prompt: Path | None | _Unset = _UNSET,
        progress_callback: TranscriptionProgressCallback | None = None,
    ) -> None:
        self.recording = MockRecording()
        super().__init__(
            recording_id=recording_id,
            model="mock",
            device="cpu",
            compute_type="test",
            language=language,
            prompt=prompt,
            progress_callback=progress_callback,
        )

    def transcribe_track(
        self,
        track: TrackChunkManifest,
        manifest: TranscriptionRunArtifact,
    ) -> None:
        """
        Transcribe all chunks belonging to one track.

        Generic implementation using transcribe_chunk().
        """
        super().transcribe_track(track, manifest)
        self.recording.phrase_offset += 1
        self.recording.time_offset += 1

    def transcribe_chunk(
        self,
        chunk: ChunkMetadata,
        track_id: str,
    ) -> ChunkTranscriptArtifact:
        """Transcribe a single chunk of audio into text."""
        mock_segments = self.recording.window(
            start=chunk.start,
            end=chunk.end,
        )

        segments = [
            TranscriptSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text,
                track_id=track_id,
                chunk_id=chunk.id,
                chunk_index=chunk.index,
                transcription_id=self.transcription.id,
            )
            for segment in mock_segments
        ]

        return ChunkTranscriptArtifact(
            metadata=self.artifact_metadata,
            track_id=track_id,
            chunk_id=chunk.id,
            chunk_index=chunk.index,
            transcription=self.transcription,
            segments=segments,
        )


def clip_text(
    text: str,
    segment_start: float,
    segment_end: float,
    window_start: float,
    window_end: float,
) -> str:
    """Clip a transcript segment to a given time window."""
    visible_start = max(
        segment_start,
        window_start,
    )

    visible_end = min(
        segment_end,
        window_end,
    )

    if visible_start >= visible_end:
        return ""

    duration = segment_end - segment_start
    ratio = len(text) / duration

    start_index = int((visible_start - segment_start) * ratio)

    end_index = int((visible_end - segment_start) * ratio)

    return text[start_index:end_index]
