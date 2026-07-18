"""Base Transcriber interface for transcription pipelines."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from dossier.artifact.base import ArtifactMetadata
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


class TranscriptionProgress(BaseModel):
    """Current transcription progress state."""

    total_tracks: int
    completed_tracks: int

    total_chunks: int
    completed_chunks: int

    current_track_id: str | None = None

    current_track_total_chunks: int = 0
    current_track_completed_chunks: int = 0

    current_chunk_id: str | None = None


class Transcriber(ABC):
    """Base Transcriber interface for transcription pipelines."""

    on_progress: TranscriptionProgressCallback | None = None
    _progress_state: TranscriptionProgress

    transcription: TranscriptionRun
    artifact_metadata: ArtifactMetadata
    chunkset: ChunkSetArtifact
    recording_id: str

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
    ) -> None:
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
        self.artifact_metadata = ArtifactMetadata(recording_id=recording_id)
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
        current_track_id: str | None | _Unset = _UNSET,
        current_chunk_id: str | None | _Unset = _UNSET,
        completed_tracks: int | _Unset = _UNSET,
        completed_chunks: int | _Unset = _UNSET,
        current_track_total_chunks: int | _Unset = _UNSET,
        current_track_completed_chunks: int | _Unset = _UNSET,
    ) -> None:
        """Update the current progress state and report it."""
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

        for track in chunk_set.tracks:
            self.transcribe_track(track, manifest)

        manifest.completed_at = datetime.now(UTC)
        manifest.save()

        return manifest

    def transcribe_track(
        self,
        track: TrackChunkManifest,
        manifest: TranscriptionRunArtifact,
    ) -> None:
        """
        Transcribe all chunks belonging to one track.

        Generic implementation using transcribe_chunk().
        """
        artifacts: list[ChunkTranscriptArtifact] = []
        self.update_progress(
            current_track_id=track.track_id,
            current_track_total_chunks=len(track.chunks),
            current_track_completed_chunks=0,
        )

        for i, chunk in enumerate(track.chunks):
            self.update_progress(
                completed_chunks=sum(1 for status in manifest.chunk_states.values() if status.completed),
                current_track_completed_chunks=i,
                current_chunk_id=chunk.id,
            )
            if manifest.chunk_states[chunk.id].completed:
                continue

            manifest.chunk_states[chunk.id].started_at = datetime.now(UTC)
            manifest.save()

            artifact = self.transcribe_chunk(chunk, track_id=track.track_id)
            artifact.save()

            manifest.chunk_states[chunk.id].completed = True
            manifest.chunk_states[chunk.id].completed_at = datetime.now(UTC)
            manifest.save()

            # Save immediately so completed chunks survive interruptions.
            artifacts.append(artifact)

        self.update_progress(
            current_track_id=None,
            current_track_total_chunks=0,
            current_track_completed_chunks=0,
            completed_tracks=self._progress_state.completed_tracks + 1,
        )

    @abstractmethod
    def transcribe_chunk(
        self,
        chunk: ChunkMetadata,
        track_id: str,
    ) -> ChunkTranscriptArtifact:
        """
        Transcribe a single audio chunk.

        Must be implemented by transcription backends.
        """
        raise NotImplementedError
