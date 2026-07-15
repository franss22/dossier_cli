"""Configuration models and TOML loading for the transcriber application."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib

from dossier.utils.dir import REPO_ROOT


@dataclass(slots=True)
class AudioConfig:
    """Audio processing settings loaded from the `[audio]` section."""

    chunk_minutes: int = 20
    overlap_seconds: int = 60
    sample_rate: int = 16000


@dataclass(slots=True)
class TranscriptionConfig:
    """Transcription model settings loaded from the `[transcription]` section."""

    model: str = "medium"
    language: str = "en"
    device: str = "cpu"
    compute_type: str = "int8"


@dataclass(slots=True)
class OutputConfig:
    """Output settings loaded from the `[output]` section."""

    directory: str = "output"
    format: list[str] = field(default_factory=lambda: ["json", "md"])


@dataclass(slots=True)
class DiarizationConfig:
    """Diarization settings loaded from the `[diarization]` section."""

    enabled: bool = False


@dataclass(slots=True)
class AnalysisConfig:
    """Analysis settings loaded from the `[analysis]` section."""

    enabled: bool = False
    provider: str = "ollama"
    model: str = "qwen3"


@dataclass(slots=True)
class ObsidianConfig:
    """Obsidian export settings loaded from the `[obsidian]` section."""

    enabled: bool = False
    vault: str = ""





@dataclass(slots=True)
class AppConfig:
    """Top-level application configuration composed from the TOML file."""

    audio: AudioConfig = field(default_factory=AudioConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    diarization: DiarizationConfig = field(default_factory=DiarizationConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    obsidian: ObsidianConfig = field(default_factory=ObsidianConfig)

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        """Build an application config from a parsed TOML dictionary."""
        return cls(
            audio=AudioConfig(**data.get("audio", {})),
            transcription=TranscriptionConfig(**data.get("transcription", {})),
            output=OutputConfig(**data.get("output", {})),
            diarization=DiarizationConfig(**data.get("diarization", {})),
            analysis=AnalysisConfig(**data.get("analysis", {})),
            obsidian=ObsidianConfig(**data.get("obsidian", {})),
        )

CONFIG_PATH = REPO_ROOT / "config.toml"

def load_config(config_path: str | Path = CONFIG_PATH) -> AppConfig:
    """Load application configuration from a TOML file."""
    path = Path(config_path)
    with path.open("rb") as f:
        raw_config = tomllib.load(f)
    return AppConfig.from_dict(raw_config)


