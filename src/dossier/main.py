"""Dossier CLI entrypoint."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated, TypeVar

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from dossier.artifact.chunks import ChunkingMode, ChunkSetArtifact
from dossier.artifact.index import IndexController
from dossier.artifact.recording import RecordingArtifact
from dossier.artifact.transcripts import CompiledTranscriptArtifact, TranscriptionRunArtifact
from dossier.pipeline.export import ExportMode, export_transcription
from dossier.pipeline.queue import QueueRequest, load_queue_file, run_queue
from dossier.pipeline.run import DEFAULT_CHUNK_SET_ID, RunError, RunRequest, run_recording
from dossier.ui.console import error, info, path_info, path_success, print_run_header, success
from dossier.ui.select import select_chunkset, select_transcript, select_transcripts
from dossier.utils.config import get_config
from dossier.utils.storage import delete_recording_directory
from dossier.utils.types import _UNSET

CONFIG = get_config()
ResolvedItem = TypeVar("ResolvedItem")

app = typer.Typer(
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command()
def hello() -> None:
    """Say hello."""
    info("Dossier CLI is available.")


@app.command("import")
def import_recording_command(
    input_file: Annotated[
        Path,
        typer.Argument(help="Input media file to ingest."),
    ],
    workspace_name: Annotated[
        str | None,
        typer.Argument(help="Human-readable name. Defaults to the input filename."),
    ] = None,
    aliases: list[str] = typer.Option([], "--alias", help="Optional alias. Repeat to add multiple aliases."),
) -> None:
    """Import a recording into the Dossier workspace."""
    from dossier.pipeline.ingest import ingest_recording

    workspace_name = workspace_name or _default_workspace_name(input_file)
    if workspace_name is None:
        raise typer.BadParameter("Could not derive a workspace name from the input file.")

    artifact = ingest_recording(
        input_file=input_file,
        workspace_name=workspace_name,
        aliases=aliases,
    )
    success(f"Imported recording: {artifact.recording.id}")
    info(f"Name: {_display_name(artifact)}")


@app.command("chunk")
def chunk_recording_command(
    recording: Annotated[str, typer.Argument(help="Recording ID or alias to chunk.")],
    chunk_minutes: int = typer.Option(CONFIG.audio.chunk_minutes, "--chunk-minutes", help="Chunk duration in minutes."),
    overlap_seconds: int = typer.Option(
        CONFIG.audio.overlap_seconds,
        "--overlap-seconds",
        help="Overlap duration in seconds.",
    ),
    mode: ChunkingMode = typer.Option(
        CONFIG.audio.chunk_mode,
        "--mode",
        help="Chunking mode: full, split, or overlap.",
    ),
) -> None:
    """Generate a chunk set for a recording."""
    from dossier.pipeline.chunk import chunk_recording

    rec = _resolve_recording_or_exit(recording)

    print_run_header(
        "Chunk Recording",
        recording={
            "id": rec.recording.id,
            "name": _display_name(rec),
        },
        chunking={
            "mode": mode.value,
            "minutes": str(chunk_minutes),
            "overlap": str(overlap_seconds),
        },
    )

    artifact = chunk_recording(
        rec_id=rec.recording.id,
        chunk_minutes=chunk_minutes,
        overlap_seconds=overlap_seconds,
        mode=mode,
    )
    success(f"Created chunk set: {artifact.chunk_run.id}")
    info(f"Tracks: {len(artifact.tracks)}")


@app.command("list")
def list_recordings_command() -> None:
    """List all recordings in the workspace."""
    from dossier.artifact.index import IndexController

    index_controller = IndexController()
    console = Console()

    table = Table(
        title="Recordings",
        box=box.SIMPLE_HEAD,
    )

    table.add_column("Name", style="cyan")
    table.add_column("Aliases", style="yellow")
    table.add_column("Recording ID", style="dim")

    for recording in index_controller.index.recordings:
        table.add_row(
            recording.display_name,
            ", ".join(recording.aliases) or "[dim]-[/]",
            recording.id,
        )

    console.print(table)
    info(f"{len(index_controller.index.recordings)} recording(s).")


@app.command("rename-recording")
def rename_recording_command(
    recording: Annotated[str, typer.Argument(help="Recording ID or alias to rename.")],
    new_name: Annotated[str, typer.Argument(help="New human-readable name.")],
) -> None:
    """Rename a recording's display name without changing its recording ID."""
    rec = _resolve_recording_or_exit(recording)
    renamed = IndexController().rename_recording(rec.recording.id, new_name)
    success(f"Renamed recording: {renamed.recording.id}")
    info(f"New name: {_display_name(renamed)}")


@app.command("delete-recording")
def delete_recording_command(
    recording: Annotated[str, typer.Argument(help="Recording ID or alias to delete.")],
    yes: bool = typer.Option(False, "--yes", help="Delete without confirmation."),
) -> None:
    """Delete a recording workspace and remove it from the index."""
    rec = _resolve_recording_or_exit(recording)

    if not yes:
        confirmed = typer.confirm(f"Delete recording '{_display_name(rec)}' ({rec.recording.id}) and all artifacts?")
        if not confirmed:
            info("Deletion cancelled.")
            raise typer.Exit(code=0)

    delete_recording_directory(rec.recording.id)
    IndexController().remove_recording(rec.recording.id)
    success(f"Deleted recording: {rec.recording.id}")


@app.command("clean-index")
def clean_index_command(
    yes: bool = typer.Option(False, "--yes", help="Remove stale index entries without confirmation."),
) -> None:
    """Remove index entries whose recording artifacts no longer exist on disk."""
    controller = IndexController()
    stale_recording_ids = [entry.id for entry in controller.index.recordings if not RecordingArtifact.exists(entry.id)]

    if not stale_recording_ids:
        info("Index is already clean.")
        return

    if not yes:
        info("Stale index entries detected:")
        for recording_id in stale_recording_ids:
            info(f"- {recording_id}")

        confirmed = typer.confirm("Remove these stale entries from the index?")
        if not confirmed:
            info("Index cleanup cancelled.")
            raise typer.Exit(code=0)

    removed = controller.clean_index()
    success(f"Removed {len(removed)} stale index entr{'y' if len(removed) == 1 else 'ies'}.")
    for recording_id in removed:
        info(recording_id)


@app.command("transcribe")
def transcribe_command(
    recording: Annotated[str, typer.Argument(help="Recording ID or alias to transcribe.")],
    chunk_set_id: str | None = typer.Option(None, "--chunk-set", help="Chunk set ID to transcribe."),
    model: str = typer.Option(CONFIG.transcription.model_size, "--model", help="Transcription model to use."),
    device: str = typer.Option(CONFIG.transcription.device, "--device", help="Device to use for transcription."),
    compute_type: str = typer.Option(
        CONFIG.transcription.compute_type,
        "--compute-type",
        help="Compute type to use for transcription.",
    ),
    language: str | None = typer.Option(
        CONFIG.transcription.language,
        "--language",
        help="Language hint for transcription.",
    ),
    prompt: Path | None = typer.Option(None, "--prompt", help="Path to a prompt file."),
) -> None:
    """Transcribe a recording's chunk set into text."""
    from dossier.pipeline.transcribe import transcribe_recording

    rec = _resolve_recording_or_exit(recording)
    chunkset = _resolve_chunk_set_or_exit(rec, chunk_set_id)

    print_run_header(
        "Transcribe Recording",
        recording={
            "id": rec.recording.id,
            "name": _display_name(rec),
        },
        transcription={
            "chunk set": chunkset.chunk_run.id,
            "model": model,
            "device": device,
            "compute": compute_type,
            "language": language or "auto-detect",
        },
    )
    start_time = datetime.now()
    info(f"Start: {start_time.isoformat()}")

    artifact = transcribe_recording(
        rec_id=rec.recording.id,
        model=model,
        device=device,
        compute_type=compute_type,
        chunkset=chunkset.chunk_run.id,
        language=language,
        prompt=prompt or _UNSET,
    )
    success(f"Completed transcription: {artifact.transcription.id}")
    end_time = datetime.now()
    info(f"End: {end_time.isoformat()}")
    info(f"Duration: {end_time - start_time}")


@app.command("run")
def run_command(
    input_file: Annotated[
        Path | None,
        typer.Argument(help="Input media file for a new run."),
    ] = None,
    recording: str | None = typer.Option(None, "--recording", help="Existing recording ID or alias to continue."),
    name: str | None = typer.Option(None, "--name", help="Human-readable recording name for new imports."),
    aliases: list[str] = typer.Option([], "--alias", help="Optional alias. Repeat to add multiple aliases."),
    chunk_set: str | None = typer.Option(None, "--chunk-set", help="Explicit chunk set ID for an existing recording."),
    model: str = typer.Option(CONFIG.transcription.model_size, help="Transcription model to use."),
    device: str = typer.Option(CONFIG.transcription.device, help="Device to use for transcription."),
    compute_type: str = typer.Option(CONFIG.transcription.compute_type, help="Compute type to use for transcription."),
    language: str | None = typer.Option(CONFIG.transcription.language, help="Language of the recording (optional)."),
    prompt: Path | None = typer.Option(None, help="Path to a prompt file (optional)."),
    export: list[ExportMode] | None = typer.Option(None, "--export", help="Export mode(s) to emit. Defaults to all."),
) -> None:
    """Run the full happy-path pipeline for one recording."""
    export_modes = tuple(export) if export else tuple(ExportMode)
    workspace_name = name or _default_workspace_name(input_file)

    if input_file is not None:
        print_run_header(
            "Run Recording",
            input={
                "file": str(input_file),
                "name": workspace_name or "-",
            },
            transcription={
                "model": model,
                "device": device,
                "compute": compute_type,
                "language": language or "auto-detect",
            },
        )
    elif recording is not None:
        print_run_header(
            "Run Recording",
            recording={
                "id": recording,
                "chunk set": chunk_set or DEFAULT_CHUNK_SET_ID,
            },
            transcription={
                "model": model,
                "device": device,
                "compute": compute_type,
                "language": language or "auto-detect",
            },
        )

    try:
        request = RunRequest(
            input_file=input_file,
            workspace_name=workspace_name,
            recording_id=recording,
            chunk_set_id=chunk_set,
            aliases=aliases,
            model=model,
            device=device,
            compute_type=compute_type,
            language=language,
            prompt=prompt or _UNSET,
            export_modes=export_modes,
        )
        result = run_recording(request)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except RunError as exc:
        _print_run_failure(exc)
        raise typer.Exit(code=1) from exc

    info(f"Run complete for recording '{_display_name(result.recording)}' ({result.recording.recording.id}).")
    success(f"Transcription: {result.transcription.transcription.id}")
    path_success("Compiled transcript", result.compiled.storage_path())
    for mode, path in result.exports.items():
        path_success(f"Exported {mode.value}", path)


@app.command("queue")
def queue_command(
    input_files: Annotated[
        list[Path] | None,
        typer.Argument(help="One or more source recordings to process sequentially."),
    ] = None,
    from_file: Path | None = typer.Option(None, "--from-file", help="Text file with one source path per line."),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Stop after the first failed queue item."),
    model: str = typer.Option(CONFIG.transcription.model_size, help="Transcription model to use."),
    device: str = typer.Option(CONFIG.transcription.device, help="Device to use for transcription."),
    compute_type: str = typer.Option(CONFIG.transcription.compute_type, help="Compute type to use for transcription."),
    language: str | None = typer.Option(CONFIG.transcription.language, help="Language of the recording (optional)."),
    prompt: Path | None = typer.Option(None, help="Path to a prompt file (optional)."),
    export: list[ExportMode] | None = typer.Option(None, "--export", help="Export mode(s) to emit. Defaults to all."),
) -> None:
    """Process multiple source recordings sequentially through the happy-path pipeline."""
    queued_files = tuple(input_files or []) + tuple(load_queue_file(from_file) if from_file is not None else [])
    if not queued_files:
        raise typer.BadParameter("Provide one or more input files or use --from-file.")

    export_modes = tuple(export) if export else tuple(ExportMode)

    print_run_header(
        "Queue Recordings",
        queue={
            "items": str(len(queued_files)),
            "fail fast": "yes" if fail_fast else "no",
        },
        transcription={
            "model": model,
            "device": device,
            "compute": compute_type,
            "language": language or "auto-detect",
        },
    )

    result = run_queue(
        QueueRequest(
            input_files=queued_files,
            model=model,
            device=device,
            compute_type=compute_type,
            export_modes=export_modes,
            fail_fast=fail_fast,
            language=language,
            prompt=prompt or _UNSET,
        )
    )

    for item in result.items:
        info(f"[{item.input_file}]")
        if item.success and item.result is not None:
            success(f"{_display_name(item.result.recording)} ({item.result.recording.recording.id})")
            for mode, path in item.result.exports.items():
                path_success(f"Exported {mode.value}", path)
        elif item.error is not None:
            error(str(item.error))

    info(f"Queue complete: {len(result.succeeded)} succeeded, {len(result.failed)} failed, {len(result.items)} total.")

    if result.failed:
        raise typer.Exit(code=1)


@app.command("compile")
def compile_transcripts_command(
    recording: Annotated[str, typer.Argument(help="Recording ID or alias to compile.")],
    new: bool = typer.Option(False, "--new", help="Compile only new (uncompiled) transcription runs."),
    transcription_id: str | None = typer.Option(None, "--transcription", help="Compile a specific transcription run."),
) -> None:
    """Compile all (uncompiled) chunk transcripts into a single transcript."""
    from dossier.pipeline.compile import compile_transcription

    rec = _resolve_recording_or_exit(recording)

    runs = TranscriptionRunArtifact.list(rec.recording.id)
    if transcription_id is not None:
        raw_transcriptions = [run for run in runs if run.transcription.id == transcription_id]
        if not raw_transcriptions:
            error(f"No transcription run '{transcription_id}' found for recording '{rec.recording.id}'.")
            raise typer.Exit(code=1)
    else:
        raw_transcriptions = [run for run in runs if not run.compiled] if new else runs

    if not raw_transcriptions:
        info("No transcription runs matched the requested compile scope.")
        return

    for transcription in raw_transcriptions:
        info(f"Compiling transcription run '{transcription.transcription.id}'...")
        compiled = compile_transcription(transcription)
        path_success("Compiled transcript", compiled.storage_path())


@app.command("export")
def export_transcripts_command(
    recording: Annotated[str, typer.Argument(help="Recording ID or alias to export.")],
    format: ExportMode = typer.Option(ExportMode.LEAN, "--format", help="Export format."),
    transcription_id: str | None = typer.Option(None, "--transcription", help="Compiled transcription ID to export."),
) -> None:
    """Export a compiled transcript in the selected format."""
    rec = _resolve_recording_or_exit(recording)
    transcript = _resolve_compiled_transcript_or_exit(rec, transcription_id)

    print_run_header(
        "Export Transcript",
        recording={
            "id": rec.recording.id,
            "name": _display_name(rec),
        },
        export={
            "transcription": transcript.transcription.id,
            "format": format.value,
        },
    )

    p = export_transcription(transcript, format)
    path_success(f"Exported {format.value}", p)


@app.command("compare")
def compare_transcripts_command(
    transcripts: Annotated[
        list[Path] | None,
        typer.Argument(help="Two or more Lean JSON exports. The first is the baseline."),
    ] = None,
    recording: str | None = typer.Option(None, "--recording", help="Browse compiled transcripts for this recording."),
    transcription: list[str] = typer.Option(
        [],
        "--transcription",
        help="Compiled transcription ID to compare. Repeat; the first is the baseline.",
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="HTML report path."),
) -> None:
    """Compare two or more transcript runs and write an HTML report."""
    from dossier.compare import compare, default_report_path, load_compiled_transcript, load_lean_json, write_report

    transcript_paths = transcripts or []
    if recording is not None and transcript_paths:
        raise typer.BadParameter("Use either transcript paths or --recording, not both.")
    if recording is None and not transcript_paths:
        raise typer.BadParameter("Provide two Lean JSON paths or use --recording.")

    if recording is None:
        if len(transcript_paths) < 2:
            raise typer.BadParameter("Provide at least two transcript paths.")
        selected = [load_lean_json(path) for path in transcript_paths]
    else:
        rec = _resolve_recording_or_exit(recording)
        available = CompiledTranscriptArtifact.list(rec.recording.id)
        if len(available) < 2:
            raise typer.BadParameter(
                f"Recording '{rec.recording.id}' needs at least two compiled transcripts to compare."
            )
        _print_compiled_transcript_settings(available)
        if transcription:
            lookup = {artifact.transcription.id: artifact for artifact in available}
            missing = [transcription_id for transcription_id in transcription if transcription_id not in lookup]
            if missing:
                raise typer.BadParameter(f"Unknown compiled transcription ID(s): {', '.join(missing)}.")
            selected_artifacts = [lookup[transcription_id] for transcription_id in transcription]
        else:
            selected_artifacts = select_transcripts(available)
        if len(selected_artifacts) < 2:
            raise typer.BadParameter("Select at least two compiled transcripts to compare.")
        selected = [load_compiled_transcript(artifact) for artifact in selected_artifacts]

    baseline, *candidates = selected
    comparisons = [compare(baseline, candidate) for candidate in candidates]
    report_path = output or default_report_path(baseline)
    write_report(baseline, comparisons, report_path)
    path_success("Comparison report", report_path)
    for result in comparisons:
        info(f"{result.candidate.label}: {result.similarity:.2%} similarity, {result.differing_words} differing words.")


def main() -> None:
    """Expose entrypoint for the Transcriber CLI."""
    app()


def _default_workspace_name(input_file: Path | None) -> str | None:
    if input_file is None:
        return None

    if input_file.name.endswith(".flac.zip"):
        return input_file.name.removesuffix(".flac.zip")

    return input_file.stem


def _resolve_recording_or_exit(recording_ref: str) -> RecordingArtifact:
    return _load_or_exit(lambda: IndexController().get_recording(recording_ref))


def _resolve_chunk_set_or_exit(
    recording: RecordingArtifact,
    chunk_set_id: str | None,
) -> ChunkSetArtifact:
    if chunk_set_id is not None:
        return _load_or_exit(lambda: ChunkSetArtifact.load(recording.recording.id, chunk_set_id))

    chunksets = ChunkSetArtifact.list(recording.recording.id)
    return _resolve_from_collection_or_exit(
        chunksets,
        empty_message=f"No chunk sets found for recording '{recording.recording.id}'. Run `dossier chunk` first.",
        selector=select_chunkset,
    )


def _resolve_compiled_transcript_or_exit(
    recording: RecordingArtifact,
    transcription_id: str | None,
) -> CompiledTranscriptArtifact:
    compiled_transcripts = CompiledTranscriptArtifact.list(recording.recording.id)
    return _resolve_from_collection_or_exit(
        compiled_transcripts,
        empty_message=(
            f"No compiled transcripts found for recording '{recording.recording.id}'. Run `dossier compile` first."
        ),
        requested_id=transcription_id,
        get_id=lambda transcript: transcript.transcription.id,
        item_label="compiled transcript",
        selector=select_transcript,
        owner_label=recording.recording.id,
    )


def _load_or_exit(loader: Callable[[], ResolvedItem]) -> ResolvedItem:
    """Run a loader and convert lookup failures into CLI exits."""
    try:
        return loader()
    except (FileNotFoundError, ValueError) as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc


def _resolve_from_collection_or_exit(
    items: list[ResolvedItem],
    *,
    empty_message: str,
    selector: Callable[[list[ResolvedItem]], ResolvedItem],
    requested_id: str | None = None,
    get_id: Callable[[ResolvedItem], str] | None = None,
    item_label: str | None = None,
    owner_label: str | None = None,
) -> ResolvedItem:
    """Resolve one artifact from a collection via explicit ID or interactive selection."""
    if not items:
        error(empty_message)
        raise typer.Exit(code=1)

    if requested_id is not None:
        if get_id is None or item_label is None:
            raise ValueError("Explicit ID resolution requires an identifier accessor and item label.")

        for item in items:
            if get_id(item) == requested_id:
                return item

        owner_suffix = f" for recording '{owner_label}'" if owner_label is not None else ""
        error(f"No {item_label} '{requested_id}' found{owner_suffix}.")
        raise typer.Exit(code=1)

    if len(items) == 1:
        return items[0]

    return selector(items)


def _print_compiled_transcript_settings(transcripts: list[CompiledTranscriptArtifact]) -> None:
    """Display compiled runs and their decoder snapshots for comparison selection."""
    table = Table(title="Compiled Transcripts", box=box.SIMPLE_HEAD)
    table.add_column("Transcription ID", style="cyan")
    table.add_column("Backend")
    table.add_column("Model")
    table.add_column("Device")
    table.add_column("Compute")
    table.add_column("Language")

    for transcript in transcripts:
        decoder = transcript.transcription.decoder
        table.add_row(
            transcript.transcription.id,
            decoder.backend,
            decoder.model or "-",
            decoder.device or "-",
            decoder.compute_type or "-",
            decoder.language or "-",
        )

    Console().print(table)


def _print_run_failure(exc: RunError) -> None:
    error(str(exc))
    info(f"Recording: {exc.recording.recording.id}")

    if exc.chunk_set is not None:
        info(f"Chunk set: {exc.chunk_set.chunk_run.id}")

    if exc.transcription is not None:
        info(f"Transcription: {exc.transcription.transcription.id}")

    if exc.compiled is not None:
        path_info("Compiled transcript", exc.compiled.storage_path())

    for mode, path in exc.exports.items():
        path_info(f"Existing export ({mode.value})", path)

    if exc.stage == "compile":
        info("Continue manually with: dossier compile <recording-id>")
        info("Then export with: dossier export <recording-id>")
    elif exc.stage == "export":
        info("Continue manually with: dossier export <recording-id>")


def _display_name(recording: object) -> str:
    """Return a best-effort human-readable recording name for CLI output."""
    display_name = getattr(recording, "display_name", None)
    if isinstance(display_name, str) and display_name:
        return display_name

    recording_meta = getattr(recording, "recording", None)
    name = getattr(recording_meta, "name", None)
    recording_id = getattr(recording_meta, "id", None)

    if isinstance(name, str) and name:
        return name
    if isinstance(recording_id, str) and recording_id:
        return recording_id
    return "unknown"


if __name__ == "__main__":
    main()
