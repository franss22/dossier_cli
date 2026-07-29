"""HTML Rendering of manual labeling interface for Dossier transcription without speaker tracks."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from dossier.artifact.index import IndexController
from dossier.artifact.transcripts.compiled import CompiledTranscriptArtifact
from dossier.utils.dir import STORAGE_ROOT
from manual_labels.quick_collapse import collapse_segments

_session_cache: dict | None = None
_session_cache_key: tuple[str, str] | None = None

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)


@app.get("/")
def index() -> FileResponse:
    """Render index.html."""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/session")
def session(
    recording_id: str,
    transcription_id: str,
) -> dict:
    """Return transcript segments and UI grouping data."""
    global _session_cache, _session_cache_key

    key = (recording_id, transcription_id)

    if _session_cache is None or _session_cache_key != key:
        transcript = CompiledTranscriptArtifact.load(recording_id, transcription_id)
        segments = transcript.segments
        _session_cache_key = key
        _session_cache = {
            "segments": [
                {
                    "id": i,
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "duration": s.duration,
                }
                for i, s in enumerate(sorted(segments, key=lambda s: s.start))
            ],
            "groups": collapse_segments(segments),
            "audio": f"/api/audio?recording_id={recording_id}",
        }

    return _session_cache


@app.get("/api/audio")
def audio(recording_id: str) -> FileResponse:
    """Return the audio file for a given recording."""
    path = STORAGE_ROOT / recording_id / "audio" / "output.wav"

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Audio file not found",
        )

    return FileResponse(
        path,
        media_type="audio/wav",
    )


@app.get("/api/recordings")
def recordings() -> list[dict]:
    """List recordings with available transcripts."""
    result = []
    ctrl = IndexController()
    index = ctrl.get_index()
    recordings = index.recordings

    for recording in recordings:
        transcripts = CompiledTranscriptArtifact.list(recording.id)

        for transcript in transcripts:
            result.append(
                {
                    "recording_id": recording.id,
                    "transcription_id": transcript.id,
                    "name": recording.display_name,
                    "tracks": len(transcript.tracks),
                }
            )

    return result
