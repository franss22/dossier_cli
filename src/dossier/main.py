"""Transcriber CLI entrypoint."""

from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from dossier.artifact.chunks import ChunkSetArtifact
from dossier.artifact.index import IndexController
from dossier.artifact.transcript import TranscriptionRunArtifact
from dossier.ui import select_chunkset
from dossier.utils.config import get_config
from dossier.utils.types import _UNSET

CONFIG = get_config()

app = typer.Typer(
    no_args_is_help=True,
)


@app.command()
def hello() -> None:
    """Say hello."""
    typer.echo("Hello from Transcriber CLI!")


@app.command("import")
def import_recording_command(
    input_file: typer.FileText = typer.Argument(..., help="Input media file."),
    workspace_name: str = typer.Argument(..., help="Human-readable name."),
    aliases: list[str] = typer.Option([], help="Optional aliases for the recording."),
) -> None:
    """Import a recording into the Transcriber CLI."""
    from dossier.pipeline.ingest import ingest_recording

    artifact = ingest_recording(
        input_file=Path(input_file.name),
        workspace_name=workspace_name,
        aliases=aliases,
    )
    typer.echo(f"Recording imported with ID: {artifact.recording.id}")


@app.command("chunk")
def chunk_recording_command(
    rec_id: str = typer.Argument(..., help="Recording ID to chunk."),
    chunk_minutes: int = typer.Option(CONFIG.audio.chunk_minutes, help="Chunk duration in minutes."),
    overlap_seconds: int = typer.Option(CONFIG.audio.overlap_seconds, help="Overlap duration in seconds."),
) -> None:
    """Chunk a recording into overlapping segments."""
    from dossier.pipeline.chunk import chunk_recording

    rec = IndexController().get_recording(rec_id)

    artifact = chunk_recording(
        rec_id=rec.id,
        chunk_minutes=chunk_minutes,
        overlap_seconds=overlap_seconds,
    )
    typer.echo(f"Recording {rec.name} chunked into {len(artifact.tracks)} tracks.")


@app.command("list")
def list_recordings_command() -> None:
    """List all recordings in the Transcriber CLI."""
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
    console.print(f"\n[dim]{len(index_controller.index.recordings)} recording(s).[/]")


@app.command("transcribe")
def transcribe_command(
    rec_id: str = typer.Argument(..., help="Recording ID to transcribe."),
    chunk_set_id: str | None = typer.Option(None, help="Chunk set ID to transcribe (optional)."),
    model: str = typer.Option(CONFIG.transcription.model_size, help="Transcription model to use."),
    device: str = typer.Option(CONFIG.transcription.device, help="Device to use for transcription."),
    compute_type: str = typer.Option(CONFIG.transcription.compute_type, help="Compute type to use for transcription."),
    language: str | None = typer.Option(CONFIG.transcription.language, help="Language of the recording (optional)."),
    prompt: Path | None = typer.Option(None, help="Path to a prompt file (optional)."),
) -> None:
    """Transcribe a recording's chunk set into text."""
    from dossier.pipeline.transcribe import transcribe_recording

    rec = IndexController().get_recording(rec_id)

    if chunk_set_id is not None:
        chunkset = ChunkSetArtifact.load(rec.id, chunk_set_id)
    else:
        chunksets = ChunkSetArtifact.list(rec.id)
        if not chunksets:
            typer.echo(f"No chunk sets found for recording '{rec.name}'. Please run the 'chunk' command first.")
            raise typer.Exit(code=1)

        chunkset = select_chunkset(chunksets)
        chunk_set_id = chunkset.chunk_run.id
    typer.echo(f"Transcribing recording '{rec.name}' using chunk set '{chunk_set_id}'...")
    typer.echo(f"Model: {model}, Device: {device}, Compute Type: {compute_type}, Language: {language or 'auto-detect'}")

    transcribe_recording(
        rec_id=rec.id,
        model=model,
        device=device,
        compute_type=compute_type,
        chunkset=chunk_set_id,
        language=language,
        prompt=prompt or _UNSET,
    )
    typer.echo(f"Transcription of recording '{rec.name}' using chunk set '{chunk_set_id}' completed.")


@app.command("merge")
def merge_transcripts_command(
    rec_id: str = typer.Argument(..., help="Recording ID to merge transcripts for."),
) -> None:
    """Merge all (unmerged) chunk transcripts into a single transcript."""
    from dossier.pipeline.merge import merge_transcription

    rec = IndexController().get_recording(rec_id)

    runs = TranscriptionRunArtifact.list(rec.id)
    unmerged_transcriptions = [run for run in runs if not run.merged]
    for transcription in unmerged_transcriptions:
        typer.echo(f"Merging transcription run '{transcription.transcription.id}' for recording '{rec.name}'...")
        merge_transcription(transcription)
        typer.echo(f"Transcription run '{transcription.transcription.id}' merged successfully.")


def main() -> None:
    """Expose entrypoint for the Transcriber CLI."""
    app()


if __name__ == "__main__":
    main()
