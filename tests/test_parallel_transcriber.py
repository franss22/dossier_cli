from __future__ import annotations

from pathlib import Path
from threading import Barrier, BrokenBarrierError, Lock, get_ident
from typing import TYPE_CHECKING
from unittest import TestCase
from unittest.mock import patch

if TYPE_CHECKING:
    from collections.abc import Callable

from dossier.artifact.base import FileMetadata
from dossier.artifact.chunks import (
    ChunkingMode,
    ChunkMetadata,
    ChunkSetArtifact,
    ChunkSetConfiguration,
    TrackChunkManifest,
)
from dossier.artifact.transcripts import ChunkTranscriptArtifact, TranscriptSegment
from dossier.artifact.transcripts.chunk import ChunkSource
from dossier.artifact.transcripts.transcription import TranscriptionRunArtifact
from dossier.transcriber.transcriber import Transcriber, TranscriptionProgress


def make_chunk(track_id: str, index: int, start: float, end: float) -> ChunkMetadata:
    return ChunkMetadata(
        id=ChunkMetadata.build_id(track_id, index),
        index=index,
        start=start,
        end=end,
        working_path=Path(f"audio/{track_id}_{index:03d}.wav"),
    )


def make_chunk_set(track_chunk_counts: dict[str, int]) -> ChunkSetArtifact:
    return ChunkSetArtifact(
        metadata=FileMetadata.new(recording_id="rec_parallel"),
        chunk_run=ChunkSetConfiguration(
            id="chunkset_full",
            duration_seconds=1200,
            overlap_seconds=0,
            mode=ChunkingMode.FULL,
        ),
        tracks=[
            TrackChunkManifest(
                track_id=track_id,
                chunks=[make_chunk(track_id, index, index * 10.0, (index + 1) * 10.0) for index in range(chunk_count)],
            )
            for track_id, chunk_count in track_chunk_counts.items()
        ],
    )


class RecordingTranscriber(Transcriber):
    backend_name = "recording"

    def __init__(
        self,
        *,
        workers: int,
        first_chunk_barrier: Barrier | None = None,
        fail_chunk_id: str | None = None,
        progress_callback: Callable[[TranscriptionProgress], None] | None = None,
    ) -> None:
        self.first_chunk_barrier = first_chunk_barrier
        self.fail_chunk_id = fail_chunk_id
        self.call_log: list[tuple[str, str, str, int]] = []
        self.log_lock = Lock()
        super().__init__(
            recording_id="rec_parallel",
            model="recording",
            device="cpu",
            compute_type="test",
            prompt=None,
            progress_callback=progress_callback,
            workers=workers,
        )

    def transcribe_chunk(
        self,
        chunk: ChunkMetadata,
        track_id: str,
    ) -> ChunkTranscriptArtifact:
        with self.log_lock:
            self.call_log.append((track_id, chunk.id, "start", get_ident()))

        if self.first_chunk_barrier is not None and chunk.index == 0:
            try:
                self.first_chunk_barrier.wait(timeout=2)
            except BrokenBarrierError as exc:
                raise RuntimeError("tracks did not start concurrently") from exc

        if self.fail_chunk_id == chunk.id:
            raise RuntimeError("boom")

        artifact = ChunkTranscriptArtifact(
            metadata=self.artifact_metadata,
            track_id=track_id,
            chunk_id=chunk.id,
            chunk_index=chunk.index,
            transcription=self.transcription,
            decoder=self.transcription.decoder,
            source=ChunkSource(
                track_id=track_id,
                chunk_id=chunk.id,
                chunk_index=chunk.index,
                start=chunk.start,
                end=chunk.end,
                duration=chunk.duration,
            ),
            segments=[
                TranscriptSegment(
                    start=chunk.start,
                    end=chunk.end,
                    text=f"{track_id}:{chunk.index}",
                    track_id=track_id,
                    chunk_id=chunk.id,
                    chunk_index=chunk.index,
                    transcription_id=self.transcription.id,
                )
            ],
        )

        with self.log_lock:
            self.call_log.append((track_id, chunk.id, "end", get_ident()))

        return artifact


class ParallelTranscriberTests(TestCase):
    def test_workers_one_preserves_serial_track_processing(self) -> None:
        progress_states: list[TranscriptionProgress] = []
        transcriber = RecordingTranscriber(
            workers=1,
            progress_callback=lambda state: progress_states.append(state.model_copy(deep=True)),
        )
        chunk_set = make_chunk_set({"track_a": 2, "track_b": 2})

        with (
            patch.object(TranscriptionRunArtifact, "save", autospec=True, return_value=Path("manifest.json")),
            patch.object(ChunkTranscriptArtifact, "save", autospec=True, return_value=Path("chunk.json")),
        ):
            manifest = transcriber.transcribe_chunk_set(chunk_set)

        self.assertIsNotNone(manifest.completed_at)
        self.assertTrue(all(state.completed for state in manifest.chunk_states.values()))
        self.assertEqual(
            [entry[:3] for entry in transcriber.call_log],
            [
                ("track_a", "track_a/000", "start"),
                ("track_a", "track_a/000", "end"),
                ("track_a", "track_a/001", "start"),
                ("track_a", "track_a/001", "end"),
                ("track_b", "track_b/000", "start"),
                ("track_b", "track_b/000", "end"),
                ("track_b", "track_b/001", "start"),
                ("track_b", "track_b/001", "end"),
            ],
        )
        self.assertEqual(len({entry[3] for entry in transcriber.call_log}), 1)
        self.assertTrue(any(state.completed_chunks == 4 for state in progress_states))

    def test_workers_two_runs_tracks_in_parallel_and_reports_multiple_active_tracks(self) -> None:
        progress_states: list[TranscriptionProgress] = []
        transcriber = RecordingTranscriber(
            workers=2,
            first_chunk_barrier=Barrier(2),
            progress_callback=lambda state: progress_states.append(state.model_copy(deep=True)),
        )
        chunk_set = make_chunk_set({"track_a": 2, "track_b": 2})

        with (
            patch.object(TranscriptionRunArtifact, "save", autospec=True, return_value=Path("manifest.json")),
            patch.object(ChunkTranscriptArtifact, "save", autospec=True, return_value=Path("chunk.json")),
        ):
            manifest = transcriber.transcribe_chunk_set(chunk_set)

        self.assertIsNotNone(manifest.completed_at)
        self.assertTrue(all(state.completed for state in manifest.chunk_states.values()))
        self.assertGreaterEqual(len({entry[3] for entry in transcriber.call_log}), 2)
        self.assertTrue(any(len(state.active_tracks) >= 2 for state in progress_states))

        track_a_events = [event[2] for event in transcriber.call_log if event[0] == "track_a"]
        track_b_events = [event[2] for event in transcriber.call_log if event[0] == "track_b"]
        self.assertEqual(track_a_events, ["start", "end", "start", "end"])
        self.assertEqual(track_b_events, ["start", "end", "start", "end"])

    def test_failure_marks_manifest_and_preserves_completed_chunks(self) -> None:
        saved_manifests: list[TranscriptionRunArtifact] = []
        transcriber = RecordingTranscriber(workers=2, fail_chunk_id="track_b/001")
        chunk_set = make_chunk_set({"track_a": 1, "track_b": 2})

        def save_manifest(manifest: TranscriptionRunArtifact) -> Path:
            saved_manifests.append(manifest)
            return Path("manifest.json")

        with (
            patch.object(TranscriptionRunArtifact, "save", autospec=True, side_effect=save_manifest),
            patch.object(ChunkTranscriptArtifact, "save", autospec=True, return_value=Path("chunk.json")),
            self.assertRaisesRegex(RuntimeError, "track_b/001"),
        ):
            transcriber.transcribe_chunk_set(chunk_set)

        last_manifest = saved_manifests[-1]
        self.assertTrue(last_manifest.chunk_states["track_a/000"].completed)
        self.assertTrue(last_manifest.chunk_states["track_b/000"].completed)
        self.assertEqual(last_manifest.chunk_states["track_b/001"].error, "boom")
        self.assertIsNone(last_manifest.completed_at)
