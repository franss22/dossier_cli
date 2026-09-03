"""Manual test for Dossier progress UI."""

import time

from dossier.ui.progress import ProgressUI, checklist


def sleep_step(seconds: float) -> None:
    """Simulate work."""
    time.sleep(seconds)


def test_progress_ui(
    delay: float = 0.5,
) -> None:
    """Exercise all progress UI features."""
    print("Testing progress UI...")

    with ProgressUI() as ui:
        # 1. Simple spinner task
        with ui.task("Loading configuration"):
            sleep_step(delay)

        # 2. Simple progress bar
        with ui.task("Processing files", total=5) as task:
            for _ in range(5):
                sleep_step(delay)
                task.advance()

        # 3. Nested mixed tasks
        with ui.task("Transcription pipeline") as pipeline:
            with pipeline.task("Preparing audio"):
                sleep_step(delay)

            with pipeline.task("Transcribing tracks", total=3) as tracks:
                for _ in range(3):
                    sleep_step(delay)
                    tracks.advance()

            with pipeline.task("Compiling transcript"):
                sleep_step(delay)

        # 4. Deep nesting
        with ui.task("Full analysis") as analysis, analysis.task("Session 1") as session:
            with session.task("Track processing", total=4) as tracks:
                for _ in range(4):
                    sleep_step(delay)
                    tracks.advance()

            with session.task("AI enrichment"):
                sleep_step(delay)

        # 5. Pipeline-style workflow
        with ui.task("Dossier pipeline") as pipeline:
            with pipeline.task("Import recording"):
                sleep_step(delay)

            with pipeline.task("Generate chunks"):
                sleep_step(delay)

            with pipeline.task("Transcribe") as transcription:
                for _ in range(3):
                    sleep_step(delay)
                    transcription.advance()

            with pipeline.task("Compile"):
                sleep_step(delay)

            with pipeline.task("Export"):
                sleep_step(delay)

        # 6. Nested unknown + known progress
        with ui.task("Batch processing") as batch:
            with batch.task("Session 1") as session:
                with session.task("Loading"):
                    sleep_step(delay)

                with session.task("Tracks", total=3) as tracks:
                    for _ in range(3):
                        sleep_step(delay)
                        tracks.advance()

            with batch.task("Session 2") as session:
                with session.task("Analyzing"):
                    sleep_step(delay)

                with session.task("Tracks", total=2) as tracks:
                    for _ in range(2):
                        sleep_step(delay)
                        tracks.advance()

        # 7. Multiple sibling progress bars
        with (
            ui.task("Parallel work") as parallel,
            parallel.task("Audio", total=4) as audio,
            parallel.task("Metadata", total=3) as metadata,
        ):
            for _ in range(3):
                sleep_step(delay)
                metadata.advance()

            for _ in range(4):
                sleep_step(delay)
                audio.advance()

    # 8. Final checklist / execution summary
    with checklist(
        "Dossier pipeline summary",
        [
            "Import recording",
            "Generate chunks",
            "Transcribe",
            "Compile transcript",
            "Export",
        ],
    ) as summary:
        for item in summary.items:
            sleep_step(delay)
            summary.complete(item)

    print("Done!")


if __name__ == "__main__":
    test_progress_ui()
