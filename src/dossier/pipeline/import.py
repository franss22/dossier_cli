"""Import pipeline for Dossier.

Processes a recording into a normalized audio format and saves it to a newly created recording workspace.
"""

from datetime import datetime, UTC
from pathlib import Path
import secrets
from typing import Any
from dossier.artifact.base import ArtifactMetadata
from dossier.storage import create_recording_directory, get_recording_path
from dossier.artifact.recording import RecordingArtifact, RecordingMetadata, RecordingSource
from orjson import loads as json_loads
from dossier.utils.dir import calculate_sha256
from dossier.utils.ffmpeg import run_ffmpeg, run_ffprobe
from dossier.utils.types import AudioStream
import zipfile
from tempfile import TemporaryDirectory
from slugify import slugify


def idify(name: str) -> str:
    """Generate a unique ID for the recording, still human readable and relevant to the workspace name."""
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    slug = slugify(name, word_boundary=True, max_length=40)
    suffix = secrets.token_hex(3)

    return f"{slug}_{date}_{suffix}"


def create_recording_artifact(
    input_file: Path,
    rec_id: str,
    workspace_name: str | None,
    tracks: list[Path],
) -> RecordingArtifact:
    """
    Create a recording artifact from an imported recording.

    Args:
        input_file: Original recording file.
        rec_id: Recording ID.
        workspace_name: Optional human-readable name.
        tracks: Generated normalized audio tracks.

    Returns:
        A populated RecordingArtifact.
    """
    workspace_path = get_recording_path(rec_id)

    return RecordingArtifact(
        recording=RecordingMetadata(
            id=rec_id,
            name=workspace_name,
        ),
        source=RecordingSource(
            filename=input_file.name,
            size_bytes=input_file.stat().st_size,
            sha256=calculate_sha256(input_file),
            original_path=str(input_file),
        ),
        tracks=[str(track.relative_to(workspace_path)) for track in tracks],
        metadata=ArtifactMetadata(recording_id=rec_id, created_at=datetime.now(UTC)),
    )


def import_recording(
    input_file: Path,
    workspace_name: str,
    aliases: list[str] | None = None,
    sample_rate: int = 16000,
) -> RecordingArtifact:
    """
    Import a recording into a new workspace.

    Args:
        input_file: Path to the input audio file.
        workspace_name: Name of the new workspace to be created.
        aliases: Optional list of aliases for the recording.
        sample_rate: Audio sample rate for the imported tracks.

    Returns:
        A populated RecordingArtifact.
    """
    rec_id = idify(workspace_name)
    if not rec_id:
        raise ValueError(
            "Failed to generate a valid recording ID. Make sure the workspace name is valid and not empty."
        )
    workspace_path = create_recording_directory(rec_id)
    input_file = Path(input_file)
    files = []
    if input_file.name.endswith(".flac.zip"):
        files = import_craig(input_file, workspace_path / "audio", sample_rate)
    elif input_file.suffix == ".mkv":
        files = import_mkv(input_file, workspace_path / "audio", sample_rate)
    else:
        raise ValueError("Unsupported input file format. Only .flac.zip (craig) and .mkv are supported.")

    return create_recording_artifact(
        input_file=input_file,
        rec_id=rec_id,
        workspace_name=workspace_name,
        tracks=files,
    )


def import_mkv(
    input_file: Path,
    output_dir: Path,
    sample_rate: int = 16000,
) -> list[Path]:
    """
    Convert an MKV file to WAV format using ffmpeg.

    Args:
        input_file: Path to the input MKV file.
        output_dir: Path to the output directory where converted files will be saved.
    """
    convert_to_wav(
        input_file=input_file,
        output_file=Path(output_dir) / "output.wav",
        stream=0,
        sample_rate=sample_rate,
        channels=1,
    )
    return [Path(output_dir) / "output.wav"]


def import_craig(
    input_file: Path,
    output_dir: Path,
    sample_rate: int = 16000,
) -> list[Path]:
    """
    Convert a Craig recording archive to normalized WAV files.

    Craig recordings are distributed as `.flac.zip` archives containing
    one FLAC file per audio track, along with additional metadata files
    such as `info.txt` and `raw.dat`.
    """
    if not input_file.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_file}")

    if not input_file.name.endswith(".flac.zip"):
        raise ValueError("Input file must have a .flac.zip extension")

    output_dir.mkdir(parents=True, exist_ok=True)

    wav_files: list[Path] = []

    with TemporaryDirectory() as temp_dir:
        extracted_dir = Path(temp_dir)

        with zipfile.ZipFile(input_file, "r") as archive:
            archive.extractall(extracted_dir)

        flac_files = sorted(extracted_dir.glob("*.flac"))

        if not flac_files:
            raise ValueError("Craig archive contains no FLAC files")

        for flac_file in flac_files:
            wav_file = output_dir / f"{flac_file.stem}.wav"

            convert_to_wav(
                input_file=flac_file,
                output_file=wav_file,
                sample_rate=sample_rate,
                channels=1,
            )

            wav_files.append(wav_file)

    return wav_files


def convert_to_wav(
    input_file: Path,
    output_file: Path,
    *,
    stream: int = 0,
    sample_rate: int = 16000,
    channels: int = 1,
) -> Path:
    """
    Convert an audio file to WAV format using ffmpeg.

    Args:
        input_file: Path to the input audio file.
        output_file: Path to the output WAV file.
        stream: Index of the audio stream to convert (default is 0).
        sample_rate: Sample rate for the output WAV file (default is 16000).
        channels: Number of audio channels for the output WAV file (default is 1).

    Returns:
        Path to the converted WAV file.
    """
    if not output_file.parent.exists():
        output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.suffix.lower() != ".wav":
        raise ValueError("Output file must have a .wav extension")

    run_ffmpeg(
        "-i",
        str(input_file),
        "-map",
        f"0:a:{stream}",  # Map the specified audio stream
        "-ar",  # Set the audio sample rate
        str(sample_rate),
        "-vn",  # No video
        "-ac",  # Set the number of audio channels
        str(channels),
        "-c:a",  # Set the audio codec
        "pcm_s16le",
        str(output_file),
    )
    return output_file


def probe_audio_streams(input_file: Path) -> list[AudioStream]:
    """Probe the audio streams of the input file."""
    result = run_ffprobe(
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index,codec_name,sample_rate,channels",
        "-of",
        "json",
        str(input_file),
    )

    data: dict[str, Any] = json_loads(result.stdout)

    return [
        {
            "index": stream["index"],
            "codec_name": stream["codec_name"],
            "sample_rate": int(stream["sample_rate"]),
            "channels": stream["channels"],
        }
        for stream in data["streams"]
    ]


def probe_duration(input_file: Path) -> float:
    """Get the duration of a media file in seconds."""
    result = run_ffprobe(
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(input_file),
    )

    data = json_loads(result.stdout)

    return float(data["format"]["duration"])
