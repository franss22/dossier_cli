from unittest import TestCase
from unittest.mock import patch

from dossier.pipeline.transcribe import transcribe_recording


class TranscribePipelineTests(TestCase):
    def test_transcribe_recording_forwards_workers_to_transcriber(self) -> None:
        fake_chunkset = object()
        fake_artifact = object()

        with (
            patch("dossier.pipeline.transcribe.ChunkSetArtifact.load", return_value=fake_chunkset),
            patch("dossier.pipeline.transcribe.transcription_progress_bar") as progress_bar,
            patch("dossier.transcriber.faster_whisper.FasterWhisperTranscriber") as transcriber_class,
        ):
            progress_bar.return_value.__enter__.return_value = None
            transcriber_class.return_value.transcribe_chunk_set.return_value = fake_artifact

            result = transcribe_recording(
                rec_id="rec_001",
                model="small",
                device="cpu",
                compute_type="int8",
                chunkset="chunkset_full",
                workers=3,
            )

        self.assertIs(result, fake_artifact)
        transcriber_class.assert_called_once_with(
            model="small",
            device="cpu",
            compute_type="int8",
            progress_callback=None,
            recording_id="rec_001",
            language=None,
            prompt=transcribe_recording.__defaults__[1],
            workers=3,
        )
        transcriber_class.return_value.transcribe_chunk_set.assert_called_once_with(fake_chunkset)
