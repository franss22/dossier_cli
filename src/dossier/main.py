"""Dossier CLI entrypoint."""

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from dossier.artifact.chunks import ChunkingMode, ChunkSetArtifact
from dossier.artifact.index import IndexController
from dossier.artifact.recording import RecordingArtifact
from dossier.artifact.transcripts import CompiledTranscriptArtifact, TranscriptionRunArtifact
from dossier.pipeline.export import ExportMode, export_transcription
from dossier.pipeline.run import RunError, RunRequest, run_recording
from dossier.ui.console import error, info, path_info, path_success, print_run_header, success
from dossier.ui.select import select_chunkset, select_transcript
from dossier.utils.config import get_config
from dossier.utils.types import _UNSET

CONFIG = get_config()

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
    info(f"Name: {artifact.recording.name or artifact.recording.id}")


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
            "name": rec.recording.name or rec.recording.id,
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
            "name": rec.recording.name or rec.recording.id,
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
                "chunk set": chunk_set or "chunkset_full",
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

    info(
        f"Run complete for recording '{result.recording.recording.name or result.recording.recording.id}'"
        f" ({result.recording.recording.id})."
    )
    success(f"Transcription: {result.transcription.transcription.id}")
    path_success("Compiled transcript", result.compiled.storage_path())
    for mode, path in result.exports.items():
        path_success(f"Exported {mode.value}", path)


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
            "name": rec.recording.name or rec.recording.id,
        },
        export={
            "transcription": transcript.transcription.id,
            "format": format.value,
        },
    )

    p = export_transcription(transcript, format)
    path_success(f"Exported {format.value}", p)


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
    try:
        return IndexController().get_recording(recording_ref)
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(code=1) from exc


def _resolve_chunk_set_or_exit(
    recording: RecordingArtifact,
    chunk_set_id: str | None,
) -> ChunkSetArtifact:
    if chunk_set_id is not None:
        try:
            return ChunkSetArtifact.load(recording.recording.id, chunk_set_id)
        except ValueError as exc:
            error(str(exc))
            raise typer.Exit(code=1) from exc

    chunksets = ChunkSetArtifact.list(recording.recording.id)
    if not chunksets:
        error(f"No chunk sets found for recording '{recording.recording.id}'. Run `dossier chunk` first.")
        raise typer.Exit(code=1)

    if len(chunksets) == 1:
        return chunksets[0]

    return select_chunkset(chunksets)


def _resolve_compiled_transcript_or_exit(
    recording: RecordingArtifact,
    transcription_id: str | None,
) -> CompiledTranscriptArtifact:
    compiled_transcripts = CompiledTranscriptArtifact.list(recording.recording.id)
    if not compiled_transcripts:
        error(f"No compiled transcripts found for recording '{recording.recording.id}'. Run `dossier compile` first.")
        raise typer.Exit(code=1)

    if transcription_id is not None:
        for transcript in compiled_transcripts:
            if transcript.transcription.id == transcription_id:
                return transcript

        error(f"No compiled transcript '{transcription_id}' found for recording '{recording.recording.id}'.")
        raise typer.Exit(code=1)

    if len(compiled_transcripts) == 1:
        return compiled_transcripts[0]

    return select_transcript(compiled_transcripts)


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


if __name__ == "__main__":
    main()
