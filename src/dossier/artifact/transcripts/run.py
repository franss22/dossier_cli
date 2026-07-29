"""Transcription run metadata."""

import secrets
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from slugify import slugify

from dossier.utils.config import get_config
from dossier.utils.timestamp import timestamp


class DecoderConfiguration(BaseModel):
    """Complete ASR decoder configuration snapshot."""

    model_config = ConfigDict(extra="allow")

    backend: str

    model: str | None = None
    compute_type: str | None = None
    device: str | None = None
    language: str | None = None

    configured_options: dict[str, Any] = Field(default_factory=dict)
    """Options explicitly set by the user."""
    runtime_options: dict[str, Any] = Field(default_factory=dict)
    """Options set by the decoder at runtime, e.g. `beam_size`."""


class TranscriptionRun(BaseModel):
    """
    Metadata about one transcription execution.

    This describes what happened, not the transcript itself.
    """

    id: str

    stage: str

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    decoder: DecoderConfiguration

    @classmethod
    def build_id(
        cls,
        model: str,
        device: str,
    ) -> str:
        """Build a unique transcription run ID."""
        return "_".join(
            [
                slugify(model),
                slugify(device),
                timestamp(),
                secrets.token_hex(4),
            ]
        )

    @classmethod
    def create(
        cls,
        stage: str,
        decoder: DecoderConfiguration | None = None,
    ) -> "TranscriptionRun":
        """Create a transcription run from current configuration."""
        if decoder is None:
            config = get_config()

            decoder = DecoderConfiguration(
                backend="faster-whisper",
                model=config.transcription.model_size,
                compute_type=config.transcription.compute_type,
                device=config.transcription.device,
                language=config.transcription.language,
            )

        return cls(
            id=cls.build_id(
                decoder.model or "unknown",
                decoder.device or "unknown",
            ),
            stage=stage,
            decoder=decoder,
        )
