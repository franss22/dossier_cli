import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from typer.testing import CliRunner

from dossier.main import app


def write_transcript(path: Path, text: str) -> None:
    """Write a minimal Lean JSON transcript export."""
    path.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "id": 0,
                        "start_time": 0,
                        "end_time": 4,
                        "duration": 4,
                        "speaker_id": "gm",
                        "text": text,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


class CompareCommandTests(TestCase):
    runner = CliRunner()

    def test_compares_multiple_lean_json_candidates_against_first_path(self) -> None:
        with TemporaryDirectory() as directory:
            directory_path = Path(directory)
            baseline = directory_path / "baseline.json"
            candidate_one = directory_path / "int8.json"
            candidate_two = directory_path / "float32.json"
            report = directory_path / "report.html"
            write_transcript(baseline, "The gate is locked")
            write_transcript(candidate_one, "The gate was locked")
            write_transcript(candidate_two, "The gate is unlocked")

            result = self.runner.invoke(
                app,
                [
                    "compare",
                    str(baseline),
                    str(candidate_one),
                    str(candidate_two),
                    "--output",
                    str(report),
                ],
            )

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertTrue(report.exists())
            document = report.read_text(encoding="utf-8")
            self.assertIn("Baseline: baseline", document)
            self.assertIn("int8", document)
            self.assertIn("float32", document)
