from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from typer.testing import CliRunner

from dossier.artifact.base import FileMetadata
from dossier.artifact.recording import AudioMetadata, RecordingArtifact, RecordingMetadata, RecordingSource
from dossier.main import app
from dossier.pipeline.export import ExportMode
from dossier.pipeline.queue import QueueRequest, load_queue_file, run_queue
from dossier.pipeline.run import RunError, RunStage
from dossier.utils.types import _UNSET


def make_run_result(recording_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        recording=SimpleNamespace(recording=SimpleNamespace(id=recording_id, name=recording_id)),
        transcription=SimpleNamespace(transcription=SimpleNamespace(id=f"tx_{recording_id}")),
        compiled=SimpleNamespace(storage_path=lambda: Path(f"{recording_id}_compiled.json")),
        exports={ExportMode.LEAN: Path(f"{recording_id}.json")},
    )


def make_run_error(recording_id: str) -> RunError:
    return RunError(
        stage=RunStage.TRANSCRIBE,
        recording=RecordingArtifact(
            recording=RecordingMetadata(id=recording_id, name=recording_id),
            source=RecordingSource(filename="", size_bytes=0, sha256="", original_path=""),
            metadata=FileMetadata.new(recording_id=recording_id),
            audio=AudioMetadata(recording_duration=0, sample_rate=16000, tracks=[]),
        ),
        cause=RuntimeError("boom"),
    )


class QueuePipelineTests(TestCase):
    runner = CliRunner()

    def test_load_queue_file_skips_blank_lines_and_comments(self) -> None:
        with TemporaryDirectory() as directory:
            queue_file = Path(directory) / "queue.txt"
            queue_file.write_text("# sessions\n\nfirst.mkv\nsecond.flac.zip\n", encoding="utf-8")

            entries = load_queue_file(queue_file)

        self.assertEqual(entries, [Path("first.mkv"), Path("second.flac.zip")])

    def test_run_queue_processes_all_items_by_default(self) -> None:
        request = QueueRequest(
            input_files=(Path("one.mkv"), Path("two.flac.zip")),
            model="small",
            device="cpu",
            compute_type="int8",
            export_modes=(ExportMode.LEAN,),
        )

        with patch(
            "dossier.pipeline.queue.run_recording",
            side_effect=[make_run_result("rec_one"), make_run_result("rec_two")],
        ) as run_recording_mock:
            result = run_queue(request)

        self.assertEqual(len(result.items), 2)
        self.assertEqual(len(result.succeeded), 2)
        self.assertEqual(len(result.failed), 0)
        first_request = run_recording_mock.call_args_list[0].args[0]
        second_request = run_recording_mock.call_args_list[1].args[0]
        self.assertEqual(first_request.workspace_name, "one")
        self.assertEqual(second_request.workspace_name, "two")
        self.assertEqual(first_request.prompt, _UNSET)

    def test_run_queue_stops_after_failure_when_fail_fast(self) -> None:
        request = QueueRequest(
            input_files=(Path("one.mkv"), Path("two.mkv"), Path("three.mkv")),
            model="small",
            device="cpu",
            compute_type="int8",
            export_modes=(ExportMode.LEAN,),
            fail_fast=True,
        )

        with patch(
            "dossier.pipeline.queue.run_recording",
            side_effect=[make_run_result("rec_one"), make_run_error("rec_two")],
        ) as run_recording_mock:
            result = run_queue(request)

        self.assertEqual(len(result.items), 2)
        self.assertEqual(len(result.succeeded), 1)
        self.assertEqual(len(result.failed), 1)
        self.assertEqual(run_recording_mock.call_count, 2)

    def test_cli_queue_supports_paths_and_from_file(self) -> None:
        result_payload = SimpleNamespace(
            items=[
                SimpleNamespace(
                    input_file=Path("one.mkv"),
                    success=True,
                    result=make_run_result("rec_one"),
                    error=None,
                ),
                SimpleNamespace(
                    input_file=Path("two.mkv"),
                    success=True,
                    result=make_run_result("rec_two"),
                    error=None,
                ),
            ],
            succeeded=[1, 2],
            failed=[],
        )

        with TemporaryDirectory() as directory:
            queue_file = Path(directory) / "queue.txt"
            queue_file.write_text("two.mkv\n", encoding="utf-8")

            with patch("dossier.main.run_queue", return_value=result_payload) as run_queue_mock:
                result = self.runner.invoke(app, ["queue", "one.mkv", "--from-file", str(queue_file)])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        request = run_queue_mock.call_args.args[0]
        self.assertEqual(request.input_files, (Path("one.mkv"), Path("two.mkv")))
        self.assertEqual(request.export_modes, tuple(ExportMode))

    def test_cli_queue_returns_nonzero_when_any_item_fails(self) -> None:
        result_payload = SimpleNamespace(
            items=[
                SimpleNamespace(
                    input_file=Path("one.mkv"),
                    success=False,
                    result=None,
                    error=make_run_error("rec_one"),
                )
            ],
            succeeded=[],
            failed=[1],
        )

        with patch("dossier.main.run_queue", return_value=result_payload):
            result = self.runner.invoke(app, ["queue", "one.mkv"])

        self.assertEqual(result.exit_code, 1, msg=result.output)
        self.assertIn("Queue complete:", result.output)
        self.assertIn("failed", result.output)
