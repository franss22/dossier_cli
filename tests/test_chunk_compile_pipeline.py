from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from dossier.artifact.base import FileMetadata
from dossier.artifact.chunks import ChunkingMode, ChunkSetConfiguration
from dossier.artifact.recording import RecordingMetadata
from dossier.artifact.transcripts.compiled import CompiledTranscriptArtifact
from dossier.artifact.transcripts.run import DecoderConfiguration, TranscriptionRun
from dossier.artifact.transcripts.transcription import TranscriptionRunArtifact
from dossier.pipeline.compile import compile_transcription


def make_run(mode: ChunkingMode) -> TranscriptionRunArtifact:
    return TranscriptionRunArtifact(
        metadata=FileMetadata.new(recording_id="rec_001"),
        chunk_states={},
        chunk_configuration=ChunkSetConfiguration.create(10, 60, mode),
        tracks=[],
        transcription=TranscriptionRun(
            id="tx_001",
            stage="transcription",
            decoder=DecoderConfiguration(backend="mock"),
        ),
    )


def make_compiled(run: TranscriptionRunArtifact) -> CompiledTranscriptArtifact:
    return CompiledTranscriptArtifact(
        metadata=run.metadata.fresh(),
        recording=RecordingMetadata(id="rec_001", name="Session 1"),
        tracks=run.tracks,
        transcription=run.transcription,
        segments=[],
    )


class ChunkConfigurationTests(TestCase):
    def test_split_mode_normalizes_overlap_to_zero(self) -> None:
        config = ChunkSetConfiguration.create(10, 60, ChunkingMode.SPLIT)

        self.assertEqual(config.overlap_seconds, 0)
        self.assertEqual(config.id, "chunkset_split_10min")

    def test_full_mode_uses_one_full_track_range(self) -> None:
        config = ChunkSetConfiguration.full()

        self.assertEqual(config.chunk_ranges(95.0), [(0.0, 95.0)])

    def test_overlap_mode_describes_overlap_in_track_message(self) -> None:
        config = ChunkSetConfiguration.create(10, 60, ChunkingMode.OVERLAP)

        self.assertIn("60s overlap", config.describe_track("track_001"))


class CompilePipelineTests(TestCase):
    def test_compile_uses_full_strategy_for_full_mode(self) -> None:
        run = make_run(ChunkingMode.FULL)
        compiled = make_compiled(run)

        with (
            patch("dossier.pipeline.compile.compile_full", return_value=[]) as compile_full_mock,
            patch("dossier.pipeline.compile.compile_split") as compile_split_mock,
            patch("dossier.pipeline.compile.compile_overlap") as compile_overlap_mock,
            patch("dossier.pipeline.compile._interleave_tracks", return_value=[]),
            patch("dossier.pipeline.compile.CompiledTranscriptArtifact.save", return_value=Path("compiled.json")),
            patch("dossier.pipeline.compile.TranscriptionRunArtifact.save", return_value=Path("run.json")),
            patch("dossier.pipeline.compile.CompiledTranscriptArtifact", return_value=compiled),
            patch(
                "dossier.pipeline.compile.RecordingArtifact.load",
                return_value=type("R", (), {"recording": RecordingMetadata(id="rec_001")})(),
            ),
        ):
            result = compile_transcription(run)

        self.assertIs(result, compiled)
        compile_full_mock.assert_called_once_with(run)
        compile_split_mock.assert_not_called()
        compile_overlap_mock.assert_not_called()

    def test_compile_uses_split_strategy_for_split_mode(self) -> None:
        run = make_run(ChunkingMode.SPLIT)
        compiled = make_compiled(run)

        with (
            patch("dossier.pipeline.compile.compile_full") as compile_full_mock,
            patch("dossier.pipeline.compile.compile_split", return_value=[]) as compile_split_mock,
            patch("dossier.pipeline.compile.compile_overlap") as compile_overlap_mock,
            patch("dossier.pipeline.compile._interleave_tracks", return_value=[]),
            patch("dossier.pipeline.compile.CompiledTranscriptArtifact.save", return_value=Path("compiled.json")),
            patch("dossier.pipeline.compile.TranscriptionRunArtifact.save", return_value=Path("run.json")),
            patch("dossier.pipeline.compile.CompiledTranscriptArtifact", return_value=compiled),
            patch(
                "dossier.pipeline.compile.RecordingArtifact.load",
                return_value=type("R", (), {"recording": RecordingMetadata(id="rec_001")})(),
            ),
        ):
            compile_transcription(run)

        compile_full_mock.assert_not_called()
        compile_split_mock.assert_called_once_with(run)
        compile_overlap_mock.assert_not_called()

    def test_compile_uses_overlap_strategy_for_overlap_mode(self) -> None:
        run = make_run(ChunkingMode.OVERLAP)
        compiled = make_compiled(run)

        with (
            patch("dossier.pipeline.compile.compile_full") as compile_full_mock,
            patch("dossier.pipeline.compile.compile_split") as compile_split_mock,
            patch("dossier.pipeline.compile.compile_overlap", return_value=[]) as compile_overlap_mock,
            patch("dossier.pipeline.compile._interleave_tracks", return_value=[]),
            patch("dossier.pipeline.compile.CompiledTranscriptArtifact.save", return_value=Path("compiled.json")),
            patch("dossier.pipeline.compile.TranscriptionRunArtifact.save", return_value=Path("run.json")),
            patch("dossier.pipeline.compile.CompiledTranscriptArtifact", return_value=compiled),
            patch(
                "dossier.pipeline.compile.RecordingArtifact.load",
                return_value=type("R", (), {"recording": RecordingMetadata(id="rec_001")})(),
            ),
        ):
            compile_transcription(run)

        compile_full_mock.assert_not_called()
        compile_split_mock.assert_not_called()
        compile_overlap_mock.assert_called_once_with(run)
