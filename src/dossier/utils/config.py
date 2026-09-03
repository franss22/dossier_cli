"""Configuration models and TOML loading for the transcriber application."""

from __future__ import annotations

import functools
import tomllib
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_type_hints

from dossier.artifact.chunks import ChunkingMode
from dossier.utils.dir import REPO_ROOT


@dataclass(slots=True)
class AudioConfig:
    """Audio processing settings loaded from the `[audio]` section."""

    chunk_minutes: int = 20
    overlap_seconds: int = 60
    sample_rate: int = 16000
    chunk_mode: ChunkingMode = ChunkingMode.FULL  # Options: "full", "split", "overlap"


@dataclass(slots=True)
class TranscriptionConfig:
    """Transcription model settings loaded from the `[transcription]` section."""

    model_size: str = "medium"
    language: str = "en"
    device: str = "cpu"
    compute_type: str = "int8"


@dataclass(slots=True)
class OutputConfig:
    """Output settings loaded from the `[output]` section."""

    directory: str = "output"
    format: list[str] = field(default_factory=lambda: ["json", "md"])


@dataclass(slots=True)
class AnalysisConfig:
    """Analysis settings loaded from the `[analysis]` section."""

    enabled: bool = False
    provider: str = "ollama"
    model: str = "qwen3"


@dataclass(slots=True)
class SpeakerConfig:
    """Speaker labeling settings loaded from the `[speakers]` section."""

    labels: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AppConfig:
    """Top-level application configuration composed from the TOML file."""

    audio: AudioConfig = field(default_factory=AudioConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    speakers: SpeakerConfig = field(default_factory=SpeakerConfig)

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        """Build an application config from a parsed TOML dictionary."""
        return cls(
            audio=AudioConfig(**data.get("audio", {})),
            transcription=TranscriptionConfig(**data.get("transcription", {})),
            output=OutputConfig(**data.get("output", {})),
            analysis=AnalysisConfig(**data.get("analysis", {})),
            speakers=SpeakerConfig(**data.get("speakers", {})),
        )

    def shadow(self, **kwargs: Any) -> AppConfig:
        """Create a new AppConfig instance with overridden values.

        This method allows for temporary overrides of configuration values without modifying the original instance.
        """
        config = deepcopy(self)

        for key, value in kwargs.items():
            if value is None:
                continue

            path = config_map().get(key)
            if path is None:
                continue

            section_name, field_name = path
            setattr(getattr(config, section_name), field_name, value)

        return config


CONFIG_PATH = REPO_ROOT / "config.toml"
hints = get_type_hints(AppConfig)


def build_config_map() -> dict[str, tuple[str, str]]:
    """Build a mapping of CLI/config keys to (section, field)."""
    data = tomllib.load(CONFIG_PATH.open("rb"))

    # Find duplicate leaf names.
    counts: dict[str, int] = {}
    for section in data.values():
        for key in section:
            counts[key] = counts.get(key, 0) + 1

    mapping: dict[str, tuple[str, str]] = {}

    for section_name, section in data.items():
        for key in section:
            # Always add the prefixed version.
            mapping[f"{section_name}_{key}"] = (section_name, key)

            # Only add the short version if it's unique.
            if counts[key] == 1:
                mapping[key] = (section_name, key)

    return mapping


@functools.cache
def config_map() -> dict[str, tuple[str, str]]:
    """Return a cached mapping of CLI/config keys to (section, field)."""
    return build_config_map()


def refresh_config_cache() -> None:
    """Clear the cached AppConfig instance and the config map."""
    get_config.cache_clear()
    config_map.cache_clear()


@functools.cache
def get_config() -> AppConfig:
    """Return a cached AppConfig instance loaded from the TOML file."""
    return load_config()


def load_config(config_path: str | Path = CONFIG_PATH) -> AppConfig:
    """Load application configuration from a TOML file."""
    path = Path(config_path)
    with path.open("rb") as f:
        raw_config = tomllib.load(f)
    return AppConfig.from_dict(raw_config)
