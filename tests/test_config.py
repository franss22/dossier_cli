from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from dossier.utils.config import load_config


class ConfigValidationTests(TestCase):
    def test_rejects_overlap_duration_that_matches_or_exceeds_chunk_length(self) -> None:
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text(
                """
[audio]
chunk_minutes = 5
overlap_seconds = 300
sample_rate = 16000
chunk_mode = "overlap"

[transcription]
model_size = "small"
language = "en"
device = "cpu"
compute_type = "int8"
workers = 1

[output]
directory = "output"
format = ["json"]

[analysis]
enabled = false
provider = "ollama"
model = "qwen3"

[speakers]
labels = {}
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "audio.overlap_seconds"):
                load_config(config_path)

    def test_rejects_non_positive_worker_count(self) -> None:
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text(
                """
[audio]
chunk_minutes = 5
overlap_seconds = 0
sample_rate = 16000
chunk_mode = "full"

[transcription]
model_size = "small"
language = "en"
device = "cpu"
compute_type = "int8"
workers = 0

[output]
directory = "output"
format = ["json"]

[analysis]
enabled = false
provider = "ollama"
model = "qwen3"

[speakers]
labels = {}
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "transcription.workers"):
                load_config(config_path)
