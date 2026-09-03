"""Artifact storage and retrieval.

Artifacts are stored as JSON files on disk and loaded into memory as Python
objects.
"""

from pathlib import Path

from dossier.artifact.base import Artifact, StoredFile
from dossier.artifact.index import Index
from dossier.utils.dir import RECORDINGS_DIR


def load_file[T: Artifact | Index](
    path: Path,
    model: type[T],
) -> T:
    """Load an artifact from disk."""
    if not path.exists():
        raise FileNotFoundError(f"Artifact file not found: {path}")
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def artifact_exists(
    artifact: Artifact,
) -> bool:
    """Return whether an artifact exists on disk."""
    return artifact.storage_path().exists()


def delete_artifact(
    artifact: Artifact,
) -> None:
    """Delete an artifact from disk."""
    artifact.storage_path().unlink(missing_ok=True)


def create_recording_directory(
    workspace_id: str,
) -> Path:
    """Create a recording workspace."""
    recording_dir = RECORDINGS_DIR / workspace_id

    recording_dir.mkdir(parents=True, exist_ok=True)

    (recording_dir / "audio").mkdir(exist_ok=True)
    (recording_dir / "chunks").mkdir(exist_ok=True)
    (recording_dir / "transcriptions").mkdir(exist_ok=True)
    (recording_dir / "compiled_transcriptions").mkdir(exist_ok=True)
    (recording_dir / "exports").mkdir(exist_ok=True)

    return recording_dir


def get_recording_path(workspace_id: str, folder: str | None = None) -> Path:
    """Get the path to a recording workspace or a subfolder."""
    recording_dir = RECORDINGS_DIR / workspace_id
    if folder:
        recording_dir = recording_dir / folder
    return recording_dir


def recording_exists(
    workspace_id: str,
) -> bool:
    """Return whether a recording workspace exists."""
    return (RECORDINGS_DIR / workspace_id).exists()


def delete_recording_directory(
    workspace_id: str,
) -> None:
    """Delete an entire recording workspace."""
    import shutil

    shutil.rmtree(
        RECORDINGS_DIR / workspace_id,
        ignore_errors=True,
    )
