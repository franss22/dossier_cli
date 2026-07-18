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


def jsonable_object(obj: Any, *, exclude: set[str] | None = None) -> dict[str, Any]:
    """Serialize an object's public attributes to a JSON-serializable dict."""
    data = jsonable(vars(obj))

    if exclude:
        for field in exclude:
            data.pop(field, None)

    return data
