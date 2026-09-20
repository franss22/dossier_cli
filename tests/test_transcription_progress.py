from unittest import TestCase

from dossier.transcriber.faster_whisper import _processed_audio_callback, _ProgressTqdm
from dossier.transcriber.transcriber import ActiveTrackProgress, TranscriptionProgress
from dossier.ui.progress import Checklist, ProgressUI, RunProgress


class TranscriptionProgressTests(TestCase):
    def test_dashboard_renders_one_task_per_active_track(self) -> None:
        ui = ProgressUI()
        run_progress = RunProgress(ui, Checklist("Pipeline", ["Transcribe"]))

        with ui.task("Transcribe") as overall, run_progress.transcription_callback(overall) as on_progress:
            on_progress(
                TranscriptionProgress(
                    total_tracks=2,
                    completed_tracks=0,
                    total_chunks=4,
                    completed_chunks=0,
                    active_tracks=[
                        ActiveTrackProgress(
                            track_id="track_a",
                            total_chunks=2,
                            completed_chunks=0,
                            current_chunk_id="track_a/000",
                            current_chunk_processed_seconds=12,
                            current_chunk_duration_seconds=60,
                        ),
                        ActiveTrackProgress(
                            track_id="track_b",
                            total_chunks=2,
                            completed_chunks=1,
                            current_chunk_id="track_b/001",
                            current_chunk_processed_seconds=24,
                            current_chunk_duration_seconds=60,
                        ),
                    ],
                )
            )

            descriptions = [task.description for task in ui.progress.tasks]
            self.assertIn("  track_a (0/2 chunks)", descriptions)
            self.assertIn("  track_b (1/2 chunks)", descriptions)

    def test_faster_whisper_progress_adapter_forwards_processed_seconds(self) -> None:
        updates: list[float] = []
        token = _processed_audio_callback.set(updates.append)

        try:
            progress = _ProgressTqdm(total=60, disable=True)
            progress.update(12.5)
            progress.close()
        finally:
            _processed_audio_callback.reset(token)

        self.assertEqual(updates, [12.5])
