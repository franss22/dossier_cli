"""Single-recording pipeline orchestration for the Dossier CLI."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from dossier.artifact.base import FileMetadata
from dossier.artifact.chunks import ChunkSetArtifact
from dossier.artifact.index import IndexController
from dossier.artifact.recording import AudioMetadata, RecordingArtifact, RecordingMetadata, RecordingSource
from dossier.artifact.transcripts import CompiledTranscriptArtifact, TranscriptionRunArtifact
from dossier.pipeline.compile import compile_transcription
from dossier.pipeline.export import ExportMode, export_transcription
from dossier.pipeline.ingest import ingest_recording
from dossier.pipeline.transcribe import transcribe_recording
from dossier.ui.progress import RunProgressStep, run_progress
from dossier.utils.types import _UNSET, _Unset

DEFAULT_CHUNK_SET_ID = "chunkset_full"


class RunStage(StrEnum):
    """Pipeline stages for a single `dossier run` execution."""

    INGEST = "ingest"
    TRANSCRIBE = "transcribe"
    COMPILE = "compile"
    EXPORT = "export"


@dataclass(slots=True)
class RunRequest:
    """Input parameters for a single-recording run."""

    model: str
    device: str
    compute_type: str
    export_modes: tuple[ExportMode, ...]
    input_file: Path | None = None
    workspace_name: str | None = None
    recording_id: str | None = None
    chunk_set_id: str | None = None
    language: str | None = None
    prompt: Path | None | _Unset = _UNSET
    aliases: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RunResult:
    """Artifacts produced by a successful single-recording run."""

    recording: RecordingArtifact
    chunk_set: ChunkSetArtifact
    transcription: TranscriptionRunArtifact
    compiled: CompiledTranscriptArtifact
    exports: dict[ExportMode, Path]


@dataclass(slots=True)
class RunError(RuntimeError):
    """Raised when a run fails after one or more stages completed."""

    stage: RunStage
    recording: RecordingArtifact
    chunk_set: ChunkSetArtifact | None = None
    transcription: TranscriptionRunArtifact | None = None
    compiled: CompiledTranscriptArtifact | None = None
    exports: dict[ExportMode, Path] = field(default_factory=dict)
    cause: Exception | None = None

    def __post_init__(self) -> None:
        """Populate the runtime error message from the failed stage."""
        detail = f"Run failed during {self.stage.value} for recording '{self.recording.recording.id}'."
        if self.cause is not None:
            detail = f"{detail} {self.cause}"
        super().__init__(detail)


def run_recording(request: RunRequest) -> RunResult:
    """Execute the happy-path pipeline for one recording."""
    _validate_run_request(request)

    with run_progress() as progress:
        with progress.stage(RunProgressStep.IMPORT):
            recording = _resolve_recording(request)

        with progress.stage(RunProgressStep.CHUNK):
            chunk_set = _resolve_chunk_set(recording, request.chunk_set_id)

        transcription: TranscriptionRunArtifact | None = None
        compiled: CompiledTranscriptArtifact | None = None
        exports: dict[ExportMode, Path] = {}

        try:
            with (
                progress.stage(RunProgressStep.TRANSCRIBE) as transcription_task,
                progress.transcription_callback(transcription_task) as progress_callback,
            ):
                transcription = transcribe_recording(
                    rec_id=recording.recording.id,
                    model=request.model,
                    device=request.device,
                    compute_type=request.compute_type,
                    chunkset=chunk_set.chunk_run.id,
                    language=request.language,
                    prompt=request.prompt,
                    progress_callback=progress_callback,
                )
        except Exception as exc:
            raise RunError(
                stage=RunStage.TRANSCRIBE,
                recording=recording,
                chunk_set=chunk_set,
                cause=exc,
            ) from exc

        try:
            with progress.stage(RunProgressStep.COMPILE):
                compiled = compile_transcription(transcription)
        except Exception as exc:
            raise RunError(
                stage=RunStage.COMPILE,
                recording=recording,
                chunk_set=chunk_set,
                transcription=transcription,
                cause=exc,
            ) from exc

        try:
            with progress.stage(RunProgressStep.EXPORT, total=len(request.export_modes)) as export_task:
                for mode in request.export_modes:
                    exports[mode] = export_transcription(compiled, mode)
                    export_task.advance()
        except Exception as exc:
            raise RunError(
                stage=RunStage.EXPORT,
                recording=recording,
                chunk_set=chunk_set,
                transcription=transcription,
                compiled=compiled,
                exports=exports,
                cause=exc,
            ) from exc

        return RunResult(
            recording=recording,
            chunk_set=chunk_set,
            transcription=transcription,
            compiled=compiled,
            exports=exports,
        )


def _validate_run_request(request: RunRequest) -> None:
    if request.input_file is not None and request.recording_id is not None:
        raise ValueError("Provide either an input file or --recording, not both.")

    if request.input_file is None and request.recording_id is None:
        raise ValueError("Provide an input file or --recording.")

    if request.input_file is not None and not request.workspace_name:
        raise ValueError("workspace_name is required when starting from an input file.")

    if request.recording_id is not None and request.workspace_name is not None:
        raise ValueError("workspace_name is only valid when starting from an input file.")

    if request.input_file is not None and request.chunk_set_id is not None:
        raise ValueError("--chunk-set can only be used with --recording.")

    if not request.export_modes:
        request.export_modes = tuple(ExportMode)


def _resolve_recording(request: RunRequest) -> RecordingArtifact:
    if request.input_file is not None:
        existing_recording = _find_existing_recording(request.input_file)
        if existing_recording is not None:
            return existing_recording

        try:
            return ingest_recording(
                input_file=request.input_file,
                workspace_name=request.workspace_name or "",
                aliases=request.aliases,
            )
        except Exception as exc:
            raise RunError(
                stage=RunStage.INGEST,
                recording=_placeholder_recording(request.workspace_name or "pending"),
                cause=exc,
            ) from exc

    return IndexController().get_recording(request.recording_id or "")


def _find_existing_recording(input_file: Path) -> RecordingArtifact | None:
    """Reuse a prior ingest when the source file already exists in the workspace."""
    return IndexController().find_recording_by_source_path(input_file)


def _resolve_chunk_set(recording: RecordingArtifact, chunk_set_id: str | None) -> ChunkSetArtifact:
    selected_chunk_set_id = chunk_set_id or DEFAULT_CHUNK_SET_ID
    return ChunkSetArtifact.load(recording.recording.id, selected_chunk_set_id)


def _placeholder_recording(workspace_name: str) -> RecordingArtifact:
    return RecordingArtifact(
        recording=RecordingMetadata(id=workspace_name, name=workspace_name),
        source=RecordingSource(filename="", size_bytes=0, sha256="", original_path=""),
        metadata=FileMetadata.new(recording_id=workspace_name),
        audio=AudioMetadata(recording_duration=0, sample_rate=16000, tracks=[]),
    )
