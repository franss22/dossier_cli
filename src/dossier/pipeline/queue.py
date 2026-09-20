"""Batch queue orchestration built on top of the single-recording run pipeline."""

from dataclasses import dataclass, field
from pathlib import Path

from dossier.pipeline.export import ExportMode
from dossier.pipeline.run import RunError, RunRequest, RunResult, run_recording
from dossier.utils.types import _UNSET, _Unset


@dataclass(slots=True)
class QueueRequest:
    """Input parameters for processing multiple source recordings sequentially."""

    input_files: tuple[Path, ...]
    model: str
    device: str
    compute_type: str
    export_modes: tuple[ExportMode, ...]
    fail_fast: bool = False
    language: str | None = None
    prompt: Path | None | _Unset = _UNSET


@dataclass(slots=True)
class QueueItemResult:
    """Outcome of one queue item."""

    input_file: Path
    success: bool
    result: RunResult | None = None
    error: RunError | None = None


@dataclass(slots=True)
class QueueResult:
    """Aggregate outcome of processing a queue snapshot."""

    items: list[QueueItemResult] = field(default_factory=list)

    @property
    def succeeded(self) -> list[QueueItemResult]:
        """Return successful queue items."""
        return [item for item in self.items if item.success]

    @property
    def failed(self) -> list[QueueItemResult]:
        """Return failed queue items."""
        return [item for item in self.items if not item.success]


def run_queue(request: QueueRequest) -> QueueResult:
    """Process a snapshot of source recordings sequentially using `run_recording`."""
    if not request.input_files:
        raise ValueError("Queue requires at least one input file.")

    result = QueueResult()
    for input_file in request.input_files:
        run_request = RunRequest(
            input_file=input_file,
            workspace_name=_default_workspace_name(input_file),
            model=request.model,
            device=request.device,
            compute_type=request.compute_type,
            export_modes=request.export_modes,
            language=request.language,
            prompt=request.prompt,
        )

        try:
            item_result = run_recording(run_request)
        except RunError as exc:
            result.items.append(
                QueueItemResult(
                    input_file=input_file,
                    success=False,
                    error=exc,
                )
            )
            if request.fail_fast:
                break
        else:
            result.items.append(
                QueueItemResult(
                    input_file=input_file,
                    success=True,
                    result=item_result,
                )
            )

    return result


def load_queue_file(path: Path) -> list[Path]:
    """Load one source recording path per line from a queue file."""
    entries: list[Path] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append(Path(stripped))
    return entries


def _default_workspace_name(input_file: Path) -> str:
    if input_file.name.endswith(".flac.zip"):
        return input_file.name.removesuffix(".flac.zip")

    return input_file.stem
