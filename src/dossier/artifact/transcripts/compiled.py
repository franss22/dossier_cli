"""Compiled transcript artifacts.

Contains the final transcript produced after combining
individual chunk transcripts.
"""

from pathlib import Path

from pydantic import Field

from dossier.artifact.base import Artifact
from dossier.artifact.recording import RecordingMetadata
from dossier.artifact.transcripts.run import TranscriptionRun
from dossier.artifact.transcripts.segment import TranscriptSegment
from dossier.artifact.transcripts.transcription import TranscriptTrack


class CompiledTranscriptArtifact(Artifact):
    """
    Final compiled transcript.

    Stored as:

        compiled_transcriptions/{transcription_id}/compiled_transcript.json
    """

    recording: RecordingMetadata

    tracks: list[TranscriptTrack] = Field(default_factory=list)

    transcription: TranscriptionRun

    segments: list[TranscriptSegment] = Field(default_factory=list)

    @property
    def id(self) -> str:
        """Unique identifier for this compiled transcript."""
        return self.transcription.id

    @classmethod
    def _path(
        cls,
        recording_id: str,
        transcription_id: str,
    ) -> Path:
        return cls.resolve_static(
            recording_id,
            f"compiled_transcriptions/{transcription_id}_compiled_transcript.json",
        )

    def storage_path(self) -> Path:
        """Exact storage location."""
        return self._path(self.metadata.recording_id, self.transcription.id)

    @classmethod
    def load(
        cls,
        recording_id: str,
        transcription_id: str,
    ) -> "CompiledTranscriptArtifact":
        """Load compiled transcript artifact."""
        return super().load(recording_id, transcription_id)

    @classmethod
    def list(
        cls,
        recording_id: str,
    ) -> list["CompiledTranscriptArtifact"]:
        """List all compiled transcript artifacts for a given recording."""
        directory = cls.resolve_static(recording_id, "compiled_transcriptions")

        if not directory.exists():
            return []

        return sorted(
            [
                cls.load(recording_id, file.name.removesuffix("_compiled_transcript.json"))
                for file in directory.iterdir()
                if file.is_file() and file.name.endswith("_compiled_transcript.json")
            ],
            key=lambda artifact: artifact.transcription.id,
        )
