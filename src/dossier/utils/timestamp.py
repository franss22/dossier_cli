"""Simple utility for generating timestamp strings."""

from datetime import UTC


def timestamp() -> str:
    """Return a timestamp string for use in file names."""
    from datetime import datetime

    return datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
