"""Transcriber CLI entrypoint."""

import os
from pathlib import Path
from typing import Annotated

import typer

from dossier.utils.config import load_config
from dossier.utils.dir import create_run_directory, REPO_ROOT
from dossier.audio import probe_audio_streams, process_recording

os.environ["PATH"] += os.pathsep + str(REPO_ROOT / "ffmpeg" / "bin")
app = typer.Typer()


@app.command()
def process_recording_command(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Input media file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output_dir: Annotated[
        Path | None,
        typer.Argument(
            help="Directory for generated files.",
            exists=False,
            file_okay=False,
            dir_okay=True,
        ),
    ] = None,
    chunk_minutes: int | None = typer.Option(None),
    overlap_seconds: int | None = typer.Option(None),
) -> None:
    """Process a recording into chunked, overlapping segments."""
    from dossier.transcribe import WhisperTranscriber

    config = load_config()
    temp_dir = create_run_directory(name=input_file.stem)
    output_dir = output_dir or temp_dir
    chunk_minutes = chunk_minutes if chunk_minutes is not None else config.audio.chunk_minutes
    overlap_seconds = overlap_seconds if overlap_seconds is not None else config.audio.overlap_seconds
    sample_rate = config.audio.sample_rate

    streams = probe_audio_streams(input_file)
    typer.echo(f"Audio streams in {input_file}:")
    for stream in streams:
        typer.echo(
            f"  Index: {stream['index']}, Codec: {stream['codec_name']}, "
            f"Sample Rate: {stream['sample_rate']}, Channels: {stream['channels']}"
        )
    chunks = process_recording(
        input_file=input_file,
        output_dir=output_dir,
        chunk_minutes=chunk_minutes,
        overlap_seconds=overlap_seconds,
        sample_rate=sample_rate,
    )

    transcriber = WhisperTranscriber(
        model_name="medium",
        device="cpu",
        compute_type="int8",
        language="es",
    )

    t = transcriber.transcribe_chunk(chunks[0])

    for segment in t:
        typer.echo(f'{segment.start:.2f} → {segment.end:.2f}   "{segment.text}"')


def main() -> None:
    """Expose entrypoint for the Transcriber CLI."""
    app()


if __name__ == "__main__":
    main()
