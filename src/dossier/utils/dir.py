"""Utility functions for directory management."""

from datetime import datetime
from pathlib import Path
import hashlib

REPO_ROOT = Path(__file__).parents[3].absolute()
"""Absolute path to the root of the repository"""

TEMP_INPUT_DIR = REPO_ROOT / "temp_input"
"""Directory for temporary input files"""

FFPROBE = REPO_ROOT / "ffmpeg" / "bin" / "ffprobe.exe"
"""Absolute path to the ffprobe executable"""
FFMPEG = REPO_ROOT / "ffmpeg" / "bin" / "ffmpeg.exe"
"""Absolute path to the ffmpeg executable"""
STORAGE_ROOT = REPO_ROOT / "storage"

RECORDINGS_DIR = STORAGE_ROOT / "recordings"
"""Directory for storing recordings and their artifacts"""


def create_run_directory(name: str = "", base_dir: Path = TEMP_INPUT_DIR) -> Path:
    """Create a unique directory for a processing run."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / f"run_{name}_{timestamp}"

    run_dir.mkdir(parents=True, exist_ok=False)

    return run_dir


def calculate_sha256(path: Path) -> str:
    """Calculate the SHA-256 hash of a file."""
    sha256 = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()
