"""Base Transcriber interface for transcription pipelines."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, CancelledError, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Event

from pydantic import BaseModel, Field

from dossier.artifact.base import FileMetadata
from dossier.artifact.chunks import ChunkMetadata, ChunkSetArtifact, TrackChunkManifest
from dossier.artifact.transcripts import (
    ChunkTranscriptArtifact,
    ChunkTranscriptionState,
    TranscriptionRun,
    TranscriptionRunArtifact,
    TranscriptTrack,
)
from dossier.artifact.transcripts.run import DecoderConfiguration
from dossier.utils.dir import REPO_ROOT
from dossier.utils.types import _UNSET, _Unset

PROMPT = REPO_ROOT / "transcription_prompt.md"
TranscriptionProgressCallback = Callable[["TranscriptionProgress"], None]


class ActiveTrackProgress(BaseModel):
    """Progress state for one currently active track."""

    track_id: str
    total_chunks: int
    completed_chunks: int
    current_chunk_id: str | None = None
    current_chunk_processed_seconds: float = 0.0
    current_chunk_duration_seconds: float = 0.0


@dataclass(slots=True)
class TrackWorkerUpdate:
    """Worker-to-coordinator update for one chunk lifecycle transition."""

    kind: str
    track_id: str
    chunk_id: str
    total_chunks: int
    completed_chunks: int
    timestamp: datetime
    processed_audio_seconds: float = 0.0
    chunk_duration_seconds: float = 0.0
    acknowledge: Event | None = None


@dataclass(slots=True)
class TrackWorkerResult:
    """Final result of processing one track."""

    track_id: str
    completed_chunks: int
    failed_chunk_id: str | None = None
    error: str | None = None
    cancelled: bool = False


class TranscriptionProgress(BaseModel):
    """Current transcription progress state."""

    total_tracks: int
    completed_tracks: int

    total_chunks: int
    completed_chunks: int

    active_tracks: list[ActiveTrackProgress] = Field(default_factory=list)

    current_track_id: str | None = None

    current_track_total_chunks: int = 0
    current_track_completed_chunks: int = 0

    current_chunk_id: str | None = None


class Transcriber(ABC):
    """Base Transcriber interface for transcription pipelines."""

    on_progress: TranscriptionProgressCallback | None = None
    _progress_state: TranscriptionProgress

    transcription: TranscriptionRun
    artifact_metadata: FileMetadata
    chunkset: ChunkSetArtifact
    recording_id: str
    workers: int

    language: str | None = None
    prompt: Path | None = None

    backend_name: str = "base"

    def __init__(
        self,
        *,
        recording_id: str,
        model: str,
        device: str,
        compute_type: str,
        language: str | None = None,
        prompt: Path | None | _Unset = PROMPT,
        progress_callback: TranscriptionProgressCallback | None = None,
        workers: int = 1,
    ) -> None:
        if workers < 1:
            raise ValueError("workers must be at least 1.")

        self.transcription = TranscriptionRun.create(
            stage="transcription",
            decoder=DecoderConfiguration(
                backend=self.backend_name,
                model=model,
                device=device,
                compute_type=compute_type,
            ),
        )
        self.on_progress = progress_callback
        self._progress_state = TranscriptionProgress(
            total_tracks=0,
            completed_tracks=0,
            total_chunks=0,
            completed_chunks=0,
        )
        self.recording_id = recording_id
        self.workers = workers
        self.artifact_metadata = FileMetadata.new(recording_id=recording_id)
        self.language = language
        self.prompt = PROMPT if isinstance(prompt, _Unset) else prompt

    def prompt_text(self) -> str | None:
        """Return the prompt text if a prompt file is provided."""
        if self.prompt and self.prompt.exists():
            return self.prompt.read_text(encoding="utf-8")
        return None

    def report_progress(self) -> None:
        """Report current progress state to the callback, if provided."""
        if self.on_progress:
            self.on_progress(self._progress_state)

    def update_progress(
        self,
        *,
        active_tracks: list[ActiveTrackProgress] | _Unset = _UNSET,
        current_track_id: str | None | _Unset = _UNSET,
        current_chunk_id: str | None | _Unset = _UNSET,
        completed_tracks: int | _Unset = _UNSET,
        completed_chunks: int | _Unset = _UNSET,
        current_track_total_chunks: int | _Unset = _UNSET,
        current_track_completed_chunks: int | _Unset = _UNSET,
    ) -> None:
        """Update the current progress state and report it."""
        if not isinstance(active_tracks, _Unset):
            self._progress_state.active_tracks = active_tracks

        if not isinstance(current_track_id, _Unset):
            self._progress_state.current_track_id = current_track_id
        if not isinstance(current_chunk_id, _Unset):
            self._progress_state.current_chunk_id = current_chunk_id
        if not isinstance(completed_tracks, _Unset):
            self._progress_state.completed_tracks = completed_tracks
        if not isinstance(completed_chunks, _Unset):
            self._progress_state.completed_chunks = completed_chunks
        if not isinstance(current_track_total_chunks, _Unset):
            self._progress_state.current_track_total_chunks = current_track_total_chunks
        if not isinstance(current_track_completed_chunks, _Unset):
            self._progress_state.current_track_completed_chunks = current_track_completed_chunks

        self.report_progress()

    def transcribe_chunk_set(
        self,
        chunk_set: ChunkSetArtifact,
    ) -> TranscriptionRunArtifact:
        """
        Transcribe all tracks and chunks in a chunk set.

        Handles orchestration. Implementations only need to provide
        transcribe_chunk().
        """
        self.chunkset = chunk_set
        self._progress_state = TranscriptionProgress(
            total_tracks=len(chunk_set.tracks),
            completed_tracks=0,
            total_chunks=sum(len(track.chunks) for track in chunk_set.tracks),
            completed_chunks=0,
        )
        manifest = TranscriptionRunArtifact(
            chunk_configuration=chunk_set.chunk_run,
            transcription=self.transcription,
            chunk_states={
                f"{chunk.id}": ChunkTranscriptionState(
                    track_id=track.track_id, chunk_id=chunk.id, chunk_index=chunk.index
                )
                for track in chunk_set.tracks
                for chunk in track.chunks
            },
            tracks=[TranscriptTrack(id=track.track_id) for track in chunk_set.tracks],
            metadata=self.artifact_metadata,
            started_at=datetime.now(UTC),
        )

        manifest.save()

        if not chunk_set.tracks:
            manifest.completed_at = datetime.now(UTC)
            manifest.save()
            return manifest

        update_queue: SimpleQueue[TrackWorkerUpdate] = SimpleQueue()
        cancel_event = Event()
        future_to_track: dict[Future[TrackWorkerResult], str] = {}
        active_tracks: dict[str, ActiveTrackProgress] = {}
        successful_tracks = 0
        failure: TrackWorkerResult | None = None

        with ThreadPoolExecutor(max_workers=min(self.workers, len(chunk_set.tracks))) as executor:
            for track in chunk_set.tracks:
                future = executor.submit(
                    self.transcribe_track,
                    track,
                    manifest,
                    report_update=update_queue.put,
                    cancel_requested=cancel_event.is_set,
                )
                future_to_track[future] = track.track_id

            while future_to_track:
                self._drain_worker_updates(
                    manifest=manifest,
                    update_queue=update_queue,
                    active_tracks=active_tracks,
                    completed_tracks=successful_tracks,
                )

                done, _ = wait(tuple(future_to_track), timeout=0.05, return_when=FIRST_COMPLETED)
                if not done:
                    continue

                self._drain_worker_updates(
                    manifest=manifest,
                    update_queue=update_queue,
                    active_tracks=active_tracks,
                    completed_tracks=successful_tracks,
                )

                for future in done:
                    track_id = future_to_track.pop(future)
                    result = self._resolve_track_future(track_id, future)
                    active_tracks.pop(track_id, None)

                    if result.error is not None:
                        failure = result
                        self._record_track_failure(manifest, result)
                        cancel_event.set()
                        for pending_future in future_to_track:
                            pending_future.cancel()
                        continue

                    if not result.cancelled:
                        successful_tracks += 1

                    self._refresh_progress(active_tracks, successful_tracks, manifest)

            self._drain_worker_updates(
                manifest=manifest,
                update_queue=update_queue,
                active_tracks=active_tracks,
                completed_tracks=successful_tracks,
            )

        if failure is not None:
            raise RuntimeError(
                f"Track '{failure.track_id}' failed on chunk '{failure.failed_chunk_id}': {failure.error}"
            )

        manifest.completed_at = datetime.now(UTC)
        manifest.save()

        return manifest

    def transcribe_track(
        self,
        track: TrackChunkManifest,
        manifest: TranscriptionRunArtifact,
        *,
        report_update: Callable[[TrackWorkerUpdate], None] | None = None,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> TrackWorkerResult:
        """
        Transcribe all chunks belonging to one track.

        Generic implementation using transcribe_chunk().
        """
        report_update = report_update or (lambda _update: None)
        cancel_requested = cancel_requested or (lambda: False)
        completed_chunks = sum(
            1 for chunk_state in manifest.get_track_chunks(track.track_id).values() if chunk_state.completed
        )
        total_chunks = len(track.chunks)

        for chunk in track.chunks:
            if manifest.chunk_states[chunk.id].completed:
                continue

            if cancel_requested():
                return TrackWorkerResult(
                    track_id=track.track_id,
                    completed_chunks=completed_chunks,
                    cancelled=True,
                )

            started_at = datetime.now(UTC)
            started_ack = Event()
            report_update(
                TrackWorkerUpdate(
                    kind="started",
                    track_id=track.track_id,
                    chunk_id=chunk.id,
                    total_chunks=total_chunks,
                    completed_chunks=completed_chunks,
                    timestamp=started_at,
                    chunk_duration_seconds=chunk.duration,
                    acknowledge=started_ack,
                )
            )
            started_ack.wait()

            if cancel_requested():
                return TrackWorkerResult(
                    track_id=track.track_id,
                    completed_chunks=completed_chunks,
                    cancelled=True,
                )

            try:
                def report_chunk_progress(
                    processed_audio_seconds: float,
                    *,
                    track_id: str = track.track_id,
                    chunk_id: str = chunk.id,
                    duration: float = chunk.duration,
                    current_completed_chunks: int = completed_chunks,
                ) -> None:
                    report_update(
                        TrackWorkerUpdate(
                            kind="progress",
                            track_id=track_id,
                            chunk_id=chunk_id,
                            total_chunks=total_chunks,
                            completed_chunks=current_completed_chunks,
                            timestamp=datetime.now(UTC),
                            processed_audio_seconds=processed_audio_seconds,
                            chunk_duration_seconds=duration,
                        )
                    )

                artifact = self.transcribe_chunk(
                    chunk,
                    track_id=track.track_id,
                    progress_callback=report_chunk_progress,
                )
                artifact.save()
            except Exception as exc:
                return TrackWorkerResult(
                    track_id=track.track_id,
                    completed_chunks=completed_chunks,
                    failed_chunk_id=chunk.id,
                    error=str(exc),
                )

            completed_chunks += 1
            report_update(
                TrackWorkerUpdate(
                    kind="completed",
                    track_id=track.track_id,
                    chunk_id=chunk.id,
                    total_chunks=total_chunks,
                    completed_chunks=completed_chunks,
                    timestamp=datetime.now(UTC),
                    processed_audio_seconds=chunk.duration,
                    chunk_duration_seconds=chunk.duration,
                )
            )

        return TrackWorkerResult(
            track_id=track.track_id,
            completed_chunks=completed_chunks,
        )

    def _drain_worker_updates(
        self,
        *,
        manifest: TranscriptionRunArtifact,
        update_queue: SimpleQueue[TrackWorkerUpdate],
        active_tracks: dict[str, ActiveTrackProgress],
        completed_tracks: int,
    ) -> None:
        while True:
            try:
                update = update_queue.get_nowait()
            except Empty:
                break

            chunk_state = manifest.chunk_states[update.chunk_id]
            if update.kind == "started":
                chunk_state.started_at = update.timestamp
                chunk_state.error = None
            elif update.kind == "completed":
                chunk_state.completed = True
                chunk_state.completed_at = update.timestamp
                chunk_state.error = None

            active_tracks[update.track_id] = ActiveTrackProgress(
                track_id=update.track_id,
                total_chunks=update.total_chunks,
                completed_chunks=update.completed_chunks,
                current_chunk_id=update.chunk_id,
                current_chunk_processed_seconds=update.processed_audio_seconds,
                current_chunk_duration_seconds=update.chunk_duration_seconds,
            )
            manifest.save()
            self._refresh_progress(active_tracks, completed_tracks, manifest)

            if update.acknowledge is not None:
                update.acknowledge.set()

    def _refresh_progress(
        self,
        active_tracks: dict[str, ActiveTrackProgress],
        completed_tracks: int,
        manifest: TranscriptionRunArtifact,
    ) -> None:
        sorted_active_tracks = [active_tracks[key] for key in sorted(active_tracks)]
        current_track = sorted_active_tracks[0] if sorted_active_tracks else None
        completed_chunks = sum(1 for status in manifest.chunk_states.values() if status.completed)

        self.update_progress(
            active_tracks=sorted_active_tracks,
            current_track_id=(current_track.track_id if current_track is not None else None),
            current_chunk_id=(current_track.current_chunk_id if current_track is not None else None),
            completed_tracks=completed_tracks,
            completed_chunks=completed_chunks,
            current_track_total_chunks=(current_track.total_chunks if current_track is not None else 0),
            current_track_completed_chunks=(current_track.completed_chunks if current_track is not None else 0),
        )

    @staticmethod
    def _resolve_track_future(
        track_id: str,
        future: Future[TrackWorkerResult],
    ) -> TrackWorkerResult:
        try:
            return future.result()
        except CancelledError:
            return TrackWorkerResult(track_id=track_id, completed_chunks=0, cancelled=True)
        except Exception as exc:
            return TrackWorkerResult(
                track_id=track_id,
                completed_chunks=0,
                error=str(exc),
            )

    def _record_track_failure(
        self,
        manifest: TranscriptionRunArtifact,
        result: TrackWorkerResult,
    ) -> None:
        if result.failed_chunk_id is not None:
            manifest.chunk_states[result.failed_chunk_id].error = result.error
        manifest.save()
        self._refresh_progress({}, self._progress_state.completed_tracks, manifest)

    @abstractmethod
    def transcribe_chunk(
        self,
        chunk: ChunkMetadata,
        track_id: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> ChunkTranscriptArtifact:
        """
        Transcribe a single audio chunk.

        Must be implemented by transcription backends.
        """
        raise NotImplementedError
