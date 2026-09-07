from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from dossier.pipeline.ingest import ingest_recording


class IngestPipelineTests(TestCase):
    def test_ingest_adds_recording_to_index_after_artifacts_are_saved(self) -> None:
        artifact = SimpleNamespace(save=lambda: None)
        chunkset = SimpleNamespace(save=lambda: None)
        index_controller = SimpleNamespace(validate_recording=lambda *_args: ["s5"], add_recording=lambda *_args: None)

        with (
            patch("dossier.pipeline.ingest.generate_recording_id", return_value="rec_001"),
            patch("dossier.pipeline.ingest.IndexController", return_value=index_controller),
            patch("dossier.pipeline.ingest.create_recording_directory", return_value=Path("recordings/rec_001")),
            patch("dossier.pipeline.ingest.import_mkv", return_value=[Path("recordings/rec_001/audio/output.wav")]),
            patch("dossier.pipeline.ingest.create_recording_artifact", return_value=artifact) as create_artifact,
            patch("dossier.pipeline.ingest.build_implicit_chunkset", return_value=chunkset),
        ):
            ingest_recording(Path("input.mkv"), "Session 1", ["s5"])

        create_artifact.assert_called_once()

    def test_ingest_validates_aliases_before_running_import(self) -> None:
        index_controller = SimpleNamespace(
            validate_recording=lambda *_args: (_ for _ in ()).throw(ValueError("Duplicate alias 's5' found in index.")),
            add_recording=lambda *_args: None,
        )

        with (
            patch("dossier.pipeline.ingest.generate_recording_id", return_value="rec_001"),
            patch("dossier.pipeline.ingest.IndexController", return_value=index_controller),
            patch("dossier.pipeline.ingest.create_recording_directory") as create_dir,
            self.assertRaisesRegex(ValueError, "Duplicate alias 's5' found in index."),
        ):
            ingest_recording(Path("input.mkv"), "Session 1", ["s5"])

        create_dir.assert_not_called()
