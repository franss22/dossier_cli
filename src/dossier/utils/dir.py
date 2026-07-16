"""Utility functions for directory management."""

from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parents[3].absolute()
"""Absolute path to the root of the repository"""

TEMP_INPUT_DIR = REPO_ROOT / "temp_input"
"""Directory for temporary input files"""


def create_run_directory(name: str = "", base_dir: Path = TEMP_INPUT_DIR) -> Path:
    """Create a unique directory for a processing run."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / f"run_{name}_{timestamp}"

    run_dir.mkdir(parents=True, exist_ok=False)

    return run_dir
