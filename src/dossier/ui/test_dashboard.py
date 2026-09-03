"""Manual test for Dossier progress dashboard."""

import time

from rich.live import Live

from dossier.ui.progress import Checklist, ProgressDashboard, ProgressUI


def sleep_step(seconds: float = 0.5) -> None:
    """Simulate work."""
    time.sleep(seconds)


def test_dashboard(
    delay: float = 0.5,
) -> None:
    """Exercise combined progress + checklist dashboard."""
    print("Testing progress dashboard...")

    checklist = Checklist(
        "Pipeline",
        [
            "Import recording",
            "Generate chunks",
            "Transcribe",
            "Compile transcript",
            "Export",
        ],
    )

    with ProgressUI() as ui:
        dashboard = ProgressDashboard(
            ui.progress,
            checklist,
        )

        with Live(dashboard, refresh_per_second=10, transient=False), ui.task("Dossier pipeline") as pipeline:
            with pipeline.task(
                "Import recording",
            ):
                sleep_step(delay)
                checklist.complete("Import recording")

            with pipeline.task(
                "Generate chunks",
            ):
                sleep_step(delay)
                checklist.complete("Generate chunks")

            with pipeline.task(
                "Transcribe",
                total=5,
            ) as transcription:
                for _ in range(5):
                    sleep_step(delay)
                    transcription.advance()

                checklist.complete("Transcribe")

            with pipeline.task(
                "Compile transcript",
            ):
                sleep_step(delay)
                checklist.complete("Compile transcript")

            with pipeline.task(
                "Export",
            ):
                sleep_step(delay)
                checklist.complete("Export")

    print("Done!")


if __name__ == "__main__":
    test_dashboard()
