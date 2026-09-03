"""Progress UI helpers for Dossier CLI."""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from enum import StrEnum
from time import perf_counter
from typing import Self

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.progress import Task as RichTask
from rich.text import Text

from dossier.transcriber.transcriber import TranscriptionProgress

console = Console()


class OptionalMofNColumn(ProgressColumn):
    """Show completion count only for determinate tasks."""

    def render(
        self,
        task: RichTask,
    ) -> Text:
        """Render completion count."""
        if task.total is None:
            return Text("")

        return Text(
            f"{task.completed:.0f}/{task.total:.0f}",
            style="progress.download",
        )


class Task:
    """A progress task that can create nested tasks."""

    def __init__(
        self,
        ui: "ProgressUI",
        task_id: TaskID,
        prefix: str = "",
    ) -> None:
        self.ui = ui
        self.task_id = task_id
        self.prefix = prefix

    def advance(
        self,
        amount: int = 1,
    ) -> None:
        """Advance task progress."""
        self.ui.progress.advance(
            self.task_id,
            amount,
        )

    def update(
        self,
        *,
        completed: int | None = None,
        total: int | None = None,
        description: str | None = None,
    ) -> None:
        """Update task state."""
        if description is not None:
            description = self._format(description)

        self.ui.progress.update(
            self.task_id,
            completed=completed,
            total=total,
            description=description,
        )

    def _format(
        self,
        description: str,
    ) -> str:
        """Apply nesting indentation."""
        return f"{self.prefix}{description}"

    @contextmanager
    def task(
        self,
        description: str,
        total: int | None = None,
    ) -> Generator["Task"]:
        """Create a nested task."""
        with self.ui.task(
            description,
            total=total,
            prefix=f"{self.prefix}  ",
        ) as task:
            yield task


class ProgressUI:
    """Shared progress manager."""

    def __init__(self) -> None:
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            OptionalMofNColumn(),
            TimeElapsedColumn(),
        )

    def __enter__(self) -> Self:
        """Allow context manager usage."""
        return self

    def __exit__(
        self,
        *_: object,
    ) -> None:
        """Cleanup."""
        self.progress.stop()

    @contextmanager
    def live(self) -> Generator[None]:
        """Display progress directly."""
        with Live(
            self.progress,
            refresh_per_second=10,
        ):
            yield

    @contextmanager
    def task(
        self,
        description: str,
        total: int | None = None,
        prefix: str = "",
    ) -> Generator[Task]:
        """Create a task.

        A task with no total is indeterminate.
        """
        task_id = self.progress.add_task(
            f"{prefix}{description}",
            total=total,
        )

        try:
            yield Task(
                self,
                task_id,
                prefix=prefix,
            )
        finally:
            self.progress.remove_task(task_id)


class ChecklistState(StrEnum):
    """Checklist item state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"


class Checklist:
    """Live-updating completion checklist."""

    def __init__(
        self,
        title: str,
        items: list[str],
    ) -> None:
        self.title = title
        self.items = dict.fromkeys(
            items,
            ChecklistState.PENDING,
        )

        if items:
            self.items[items[0]] = ChecklistState.RUNNING

        self.started = perf_counter()
        self.live: Live | None = None
        self.finished = False

    def complete(
        self,
        item: str,
    ) -> None:
        """Complete item and start next item."""
        self.items[item] = ChecklistState.COMPLETE

        started_next = False

        for key, state in self.items.items():
            if key == item:
                started_next = True
                continue

            if started_next and state == ChecklistState.PENDING:
                self.items[key] = ChecklistState.RUNNING
                break

        if self.live:
            self.live.refresh()

    def finish(self) -> None:
        """Mark checklist completed."""
        self.finished = True

    def render(self) -> RenderableType:
        """Render checklist."""
        elapsed = perf_counter() - self.started

        lines: list[Text] = []

        for item, done in self.items.items():
            match done:
                case ChecklistState.PENDING:
                    symbol = "○"
                case ChecklistState.RUNNING:
                    symbol = "▶"
                case ChecklistState.COMPLETE:
                    symbol = "✓"

            lines.append(Text(f"{symbol} {item}"))

        lines.append(
            Text(
                f"\nElapsed: {elapsed:.1f}s",
                style="dim",
            )
        )

        if self.finished:
            lines.append(
                Text(
                    "\nCompleted!",
                    style="bold green",
                )
            )

        return Panel(
            Text("\n").join(lines),
            title=self.title,
            expand=False,
        )

    def __rich__(self) -> RenderableType:
        """Render checklist."""
        return self.render()


@contextmanager
def checklist(
    title: str,
    items: list[str],
) -> Generator[Checklist]:
    """Display a live checklist."""
    value = Checklist(
        title,
        items,
    )

    with Live(
        value,
        refresh_per_second=10,
        transient=False,
    ) as live:
        try:
            yield value
        finally:
            value.finish()
            live.update(
                value.render(),
                refresh=True,
            )


class ProgressDashboard:
    """Dashboard combining progress and checklist."""

    def __init__(
        self,
        progress: Progress,
        checklist: Checklist,
    ) -> None:
        self.progress = progress
        self.checklist = checklist

    def __rich__(self) -> RenderableType:
        """Render dashboard."""
        return Group(
            self.checklist,
            self.progress,
        )


@contextmanager
def dashboard(
    ui: ProgressUI,
    checklist: Checklist,
) -> Generator[ProgressDashboard]:
    """Display a progress dashboard."""
    value = ProgressDashboard(
        ui.progress,
        checklist,
    )

    with Live(
        value,
        refresh_per_second=10,
        transient=False,
    ):
        yield value


@contextmanager
def transcription_progress_bar() -> Generator[Callable[[TranscriptionProgress], None]]:
    """Compatibility wrapper for transcription pipeline."""
    with ProgressUI() as ui, ui.live(), ui.task("Overall") as overall, overall.task("Tracks") as tracks:

        def on_progress(
            state: TranscriptionProgress,
        ) -> None:
            overall.update(
                total=state.total_chunks,
                completed=state.completed_chunks,
                description=(f"Overall ({state.completed_tracks}/{state.total_tracks} tracks)"),
            )

            tracks.update(
                total=state.current_track_total_chunks,
                completed=state.current_track_completed_chunks,
                description=state.current_track_id,
            )

        yield on_progress
