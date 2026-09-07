from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from typer.testing import CliRunner

from dossier.main import app
from dossier.pipeline.export import ExportMode
from dossier.pipeline.run import DEFAULT_CHUNK_SET_ID, RunError, RunRequest, RunStage, run_recording
from dossier.ui.console import _path_message
from dossier.utils.types import _UNSET


class FakeTask:
    def advance(self, _amount: int = 1) -> None:
        return None

    def update(self, **_kwargs: object) -> None:
        return None


class FakeStageContext:
    def __enter__(self) -> FakeTask:
        return FakeTask()

    def __exit__(self, *_exc: object) -> None:
        return None


class FakeCallbackContext:
    def __enter__(self) -> object:
        return lambda _state: None

    def __exit__(self, *_exc: object) -> None:
        return None


class FakeRunProgress:
    def stage(self, *_args: object, **_kwargs: object) -> FakeStageContext:
        return FakeStageContext()

    def transcription_callback(self, _task: FakeTask) -> FakeCallbackContext:
        return FakeCallbackContext()


class FakeRunProgressContext:
    def __enter__(self) -> FakeRunProgress:
        return FakeRunProgress()

    def __exit__(self, *_exc: object) -> None:
        return None


def make_recording(recording_id: str = "rec_001") -> SimpleNamespace:
    return SimpleNamespace(recording=SimpleNamespace(id=recording_id, name="Session 1"))


def make_chunk_set(chunk_set_id: str = DEFAULT_CHUNK_SET_ID) -> SimpleNamespace:
    return SimpleNamespace(chunk_run=SimpleNamespace(id=chunk_set_id))


def make_transcription(transcription_id: str = "tx_001") -> SimpleNamespace:
    return SimpleNamespace(transcription=SimpleNamespace(id=transcription_id))


def make_compiled() -> SimpleNamespace:
    return SimpleNamespace(
        transcription=SimpleNamespace(id="tx_001"),
        storage_path=lambda: Path("compiled.json"),
    )


class RunPipelineTests(TestCase):
    runner = CliRunner()

    def test_path_message_uses_clickable_filename_and_compact_location(self) -> None:
        path = Path("F:/REPOS/dossier_cli/storage/recordings/rec_001/exports/result.md")

        message = _path_message("[green]✓[/green]", "Exported llm", path)

        self.assertEqual(message.plain, "✓ Exported llm: result.md (storage/recordings/rec_001/exports/result.md)")
        self.assertIn("link file:///", str(message.spans[1].style))

    def test_run_from_input_uses_implicit_full_chunkset_and_all_stages(self) -> None:
        request = RunRequest(
            input_file=Path("input.mkv"),
            workspace_name="Session 1",
            model="small",
            device="cpu",
            compute_type="int8",
            export_modes=(ExportMode.LEAN, ExportMode.LLM),
        )
        recording = make_recording()
        chunk_set = make_chunk_set()
        transcription = make_transcription()
        compiled = make_compiled()

        with (
            patch("dossier.pipeline.run.run_progress", return_value=FakeRunProgressContext()),
            patch("dossier.pipeline.run.ingest_recording", return_value=recording) as ingest,
            patch("dossier.pipeline.run.ChunkSetArtifact.load", return_value=chunk_set) as load_chunk_set,
            patch("dossier.pipeline.run.transcribe_recording", return_value=transcription) as transcribe,
            patch("dossier.pipeline.run.compile_transcription", return_value=compiled) as compile_run,
            patch(
                "dossier.pipeline.run.export_transcription",
                side_effect=[Path("lean.json"), Path("llm.md")],
            ) as export_run,
        ):
            result = run_recording(request)

        ingest.assert_called_once_with(
            input_file=Path("input.mkv"),
            workspace_name="Session 1",
            aliases=[],
        )
        load_chunk_set.assert_called_once_with("rec_001", DEFAULT_CHUNK_SET_ID)
        transcribe.assert_called_once_with(
            rec_id="rec_001",
            model="small",
            device="cpu",
            compute_type="int8",
            chunkset=DEFAULT_CHUNK_SET_ID,
            language=None,
            prompt=_UNSET,
            progress_callback=transcribe.call_args.kwargs["progress_callback"],
        )
        self.assertIsNotNone(transcribe.call_args.kwargs["progress_callback"])
        compile_run.assert_called_once_with(transcription)
        self.assertEqual(export_run.call_count, 2)
        self.assertEqual(result.exports[ExportMode.LEAN], Path("lean.json"))
        self.assertEqual(result.exports[ExportMode.LLM], Path("llm.md"))

    def test_run_from_input_reuses_existing_imported_recording(self) -> None:
        request = RunRequest(
            input_file=Path("input.mkv"),
            workspace_name="Session 1",
            model="small",
            device="cpu",
            compute_type="int8",
            export_modes=(ExportMode.LEAN,),
        )
        recording = make_recording()
        chunk_set = make_chunk_set()
        transcription = make_transcription()
        compiled = make_compiled()

        with (
            patch("dossier.pipeline.run.run_progress", return_value=FakeRunProgressContext()),
            patch("dossier.pipeline.run._find_existing_recording", return_value=recording),
            patch("dossier.pipeline.run.ingest_recording") as ingest,
            patch("dossier.pipeline.run.ChunkSetArtifact.load", return_value=chunk_set),
            patch("dossier.pipeline.run.transcribe_recording", return_value=transcription),
            patch("dossier.pipeline.run.compile_transcription", return_value=compiled),
            patch("dossier.pipeline.run.export_transcription", return_value=Path("lean.json")),
        ):
            result = run_recording(request)

        ingest.assert_not_called()
        self.assertEqual(result.recording, recording)

    def test_run_input_reuses_recording_after_transcribe_failure(self) -> None:
        existing_recording = make_recording("rec_existing")
        result_payload = SimpleNamespace(
            recording=existing_recording,
            transcription=make_transcription(),
            compiled=make_compiled(),
            exports={ExportMode.LEAN: Path("lean.json")},
        )

        with (
            patch("dossier.main.print_run_header"),
            patch("dossier.main.run_recording", return_value=result_payload) as run_command,
        ):
            result = self.runner.invoke(
                app,
                [
                    "run",
                    "F:/REPOS/ImpossibleLandscapes/Recordings/Session5.flac.zip",
                    "--name",
                    "delta green session 5",
                ],
            )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        request = run_command.call_args.args[0]
        self.assertEqual(request.input_file, Path("F:/REPOS/ImpossibleLandscapes/Recordings/Session5.flac.zip"))

    def test_run_from_existing_recording_uses_override_chunkset(self) -> None:
        request = RunRequest(
            recording_id="rec_001",
            chunk_set_id="chunkset_split_10min",
            model="small",
            device="cpu",
            compute_type="int8",
            export_modes=(ExportMode.LEAN,),
        )
        recording = make_recording()
        chunk_set = make_chunk_set("chunkset_split_10min")
        transcription = make_transcription()
        compiled = make_compiled()

        with (
            patch("dossier.pipeline.run.run_progress", return_value=FakeRunProgressContext()),
            patch("dossier.pipeline.run.IndexController") as index_controller,
            patch("dossier.pipeline.run.ChunkSetArtifact.load", return_value=chunk_set) as load_chunk_set,
            patch("dossier.pipeline.run.transcribe_recording", return_value=transcription),
            patch("dossier.pipeline.run.compile_transcription", return_value=compiled),
            patch("dossier.pipeline.run.export_transcription", return_value=Path("lean.json")),
        ):
            index_controller.return_value.get_recording.return_value = recording
            result = run_recording(request)

        index_controller.return_value.get_recording.assert_called_once_with("rec_001")
        load_chunk_set.assert_called_once_with("rec_001", "chunkset_split_10min")
        self.assertEqual(result.chunk_set.chunk_run.id, "chunkset_split_10min")

    def test_export_failure_preserves_previous_artifacts_in_exception(self) -> None:
        request = RunRequest(
            recording_id="rec_001",
            model="small",
            device="cpu",
            compute_type="int8",
            export_modes=(ExportMode.LEAN, ExportMode.LLM),
        )
        recording = make_recording()
        chunk_set = make_chunk_set()
        transcription = make_transcription()
        compiled = make_compiled()

        with (
            patch("dossier.pipeline.run.run_progress", return_value=FakeRunProgressContext()),
            patch("dossier.pipeline.run.IndexController") as index_controller,
            patch("dossier.pipeline.run.ChunkSetArtifact.load", return_value=chunk_set),
            patch("dossier.pipeline.run.transcribe_recording", return_value=transcription),
            patch("dossier.pipeline.run.compile_transcription", return_value=compiled),
            patch(
                "dossier.pipeline.run.export_transcription",
                side_effect=[Path("lean.json"), ValueError("boom")],
            ),
        ):
            index_controller.return_value.get_recording.return_value = recording

            with self.assertRaises(RunError) as exc_info:
                run_recording(request)

        self.assertEqual(exc_info.exception.stage, RunStage.EXPORT)
        self.assertEqual(exc_info.exception.transcription, transcription)
        self.assertEqual(exc_info.exception.compiled, compiled)
        self.assertEqual(exc_info.exception.exports, {ExportMode.LEAN: Path("lean.json")})

    def test_cli_run_from_input_derives_name_and_defaults_to_all_exports(self) -> None:
        result_payload = SimpleNamespace(
            recording=make_recording(),
            transcription=make_transcription(),
            compiled=SimpleNamespace(
                storage_path=lambda: Path("compiled.json"),
                transcription=SimpleNamespace(id="tx_001"),
            ),
            exports={ExportMode.LEAN: Path("lean.json"), ExportMode.LLM: Path("llm.md")},
        )

        with patch("dossier.main.run_recording", return_value=result_payload) as run_command:
            result = self.runner.invoke(app, ["run", "session-01.mkv"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        request = run_command.call_args.args[0]
        self.assertIsInstance(request, RunRequest)
        self.assertEqual(request.input_file, Path("session-01.mkv"))
        self.assertEqual(request.workspace_name, "session-01")
        self.assertIsNone(request.recording_id)
        self.assertEqual(request.export_modes, tuple(ExportMode))
        self.assertIn("compiled.json", result.output)
        self.assertIn("lean.json", result.output)
        self.assertIn("llm.md", result.output)

    def test_cli_run_existing_recording_accepts_chunkset_and_export_overrides(self) -> None:
        result_payload = SimpleNamespace(
            recording=make_recording(),
            transcription=make_transcription(),
            compiled=make_compiled(),
            exports={ExportMode.LEAN: Path("lean.json")},
        )

        with patch("dossier.main.run_recording", return_value=result_payload) as run_command:
            result = self.runner.invoke(
                app,
                [
                    "run",
                    "--recording",
                    "rec_001",
                    "--chunk-set",
                    "chunkset_split_10min",
                    "--export",
                    "lean",
                ],
            )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        request = run_command.call_args.args[0]
        self.assertEqual(request.recording_id, "rec_001")
        self.assertEqual(request.chunk_set_id, "chunkset_split_10min")
        self.assertIsNone(request.input_file)
        self.assertEqual(request.export_modes, (ExportMode.LEAN,))

    def test_import_command_defaults_name_from_input_file(self) -> None:
        artifact = SimpleNamespace(recording=SimpleNamespace(id="rec_001", name="session-01"))

        with patch("dossier.pipeline.ingest.ingest_recording", return_value=artifact) as ingest:
            result = self.runner.invoke(app, ["import", "session-01.mkv"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        ingest.assert_called_once_with(
            input_file=Path("session-01.mkv"),
            workspace_name="session-01",
            aliases=[],
        )

    def test_transcribe_uses_only_chunkset_without_selector_prompt(self) -> None:
        recording = make_recording()
        chunkset = make_chunk_set()
        artifact = make_transcription()

        with (
            patch("dossier.main.IndexController") as index_controller,
            patch("dossier.main.ChunkSetArtifact.list", return_value=[chunkset]),
            patch("dossier.main.select_chunkset") as select_chunkset,
            patch("dossier.pipeline.transcribe.transcribe_recording", return_value=artifact) as transcribe,
        ):
            index_controller.return_value.get_recording.return_value = recording
            result = self.runner.invoke(app, ["transcribe", "rec_001"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        select_chunkset.assert_not_called()
        transcribe.assert_called_once()
        self.assertEqual(transcribe.call_args.kwargs["chunkset"], DEFAULT_CHUNK_SET_ID)

    def test_export_uses_only_compiled_transcript_without_selector_prompt(self) -> None:
        recording = make_recording()
        transcript = make_compiled()

        with (
            patch("dossier.main.IndexController") as index_controller,
            patch("dossier.main.CompiledTranscriptArtifact.list", return_value=[transcript]),
            patch("dossier.main.select_transcript") as select_transcript,
            patch("dossier.main.export_transcription", return_value=Path("lean.json")) as export,
        ):
            index_controller.return_value.get_recording.return_value = recording
            result = self.runner.invoke(app, ["export", "rec_001", "--format", "lean"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        select_transcript.assert_not_called()
        export.assert_called_once_with(transcript, ExportMode.LEAN)
