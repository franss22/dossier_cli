"""Helper functions for serializing objects to JSON."""

from collections.abc import Mapping
from enum import Enum
from numbers import Number
from pathlib import Path
from typing import Any

import numpy as np


def jsonable(value: Any) -> Any:
    """Convert an object to a JSON-serializable format."""
    if value is None or isinstance(value, (str, bool)):
        return value

    if isinstance(value, Number):
        return value

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, np.generic):
        return value.item()

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, Mapping):
        return {k: jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]

    if hasattr(value, "__dict__"):
        return {k: jsonable(v) for k, v in vars(value).items() if not k.startswith("_")}

    return str(value)


def jsonable_object(
    obj: Any,
    *,
    exclude: set[str] | None = None,
) -> dict[str, Any]:
    """
    Serialize an object's public attributes to a JSON-serializable dict.

    Supports nested exclusions using dot notation.

    Example:
        exclude={
            "words",
            "transcription_options.suppress_tokens",
            "transcription_options.initial_prompt",
            "decoder.some.deep.field",
        }
    """
    data = jsonable(vars(obj))

    if not exclude:
        return data

    for path in exclude:
        parts = path.split(".")
        current = data

        for key in parts[:-1]:
            if not isinstance(current, dict):
                break

            current = current.get(key)

            if current is None:
                break
        else:
            if isinstance(current, dict):
                current.pop(parts[-1], None)

    return data
