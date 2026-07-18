"""Helper functions for progress bars."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import questionary
from rich.progress import Progress

from dossier.artifact.chunks import ChunkSetArtifact
from dossier.transcriber.transcriber import TranscriptionProgress


@contextmanager
def transcription_progress_bar() -> Iterator[Callable[[TranscriptionProgress], None]]:
    """Create a transcription progress callback with Rich progress bars."""
    with Progress() as progress:
        overall = progress.add_task(
            "Overall",
            total=0,
        )

        track = progress.add_task(
            "Track",
            total=0,
        )

        def on_progress(state: TranscriptionProgress) -> None:
            progress.update(
                overall,
                total=state.total_chunks,
                completed=state.completed_chunks,
                description=(f"Overall ({state.completed_tracks}/{state.total_tracks} tracks)"),
            )

            progress.update(
                track,
                total=state.current_track_total_chunks,
                completed=state.current_track_completed_chunks,
                description=(
                    f"{state.current_track_id} "
                    f"({state.current_track_completed_chunks}/{state.current_track_total_chunks} chunks)"
                ),
            )

        yield on_progress


def select_chunkset(chunksets: list[ChunkSetArtifact]) -> ChunkSetArtifact:
    """Prompt the user to select a chunk set."""
    if len(chunksets) == 1:
        return chunksets[0]

    choices = [
        questionary.Choice(
            title=(
                f"{chunkset.chunk_run.id} "
                f"({chunkset.chunk_run.duration_seconds}s chunks, "
                f"{chunkset.chunk_run.overlap_seconds}s overlap)"
            ),
            value=chunkset,
        )
        for chunkset in chunksets
    ]
    chunk = questionary.select(
        "Select chunk set:",
        choices=choices,
    ).ask()
    if chunk is None:
        raise RuntimeError("No chunk set selected.")

    return chunk
