"""Merged transcript artifacts.

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


class MergedTranscriptArtifact(Artifact):
    """
    Final merged transcript.

    Stored as:

        merged_transcriptions/{transcription_id}/merged_transcript.json
    """

    recording: RecordingMetadata

    tracks: list[TranscriptTrack] = Field(default_factory=list)

    transcription: TranscriptionRun

    segments: list[TranscriptSegment] = Field(default_factory=list)

    def storage_path(self) -> Path:
        """Exact storage location."""
        return self.workspace_path() / "merged_transcriptions" / self.transcription.id / "merged_transcript.json"

    @classmethod
    def load(
        cls,
        recording_id: str,
        transcription_id: str,
    ) -> "MergedTranscriptArtifact":
        """Load merged transcript artifact."""
        from dossier.utils.storage import load_file

        path = (
            cls.workspace_path_static(recording_id)
            / "merged_transcriptions"
            / transcription_id
            / "merged_transcript.json"
        )

        return load_file(path, cls)
