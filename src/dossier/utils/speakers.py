"""Utility functions for working with speakers in transcripts.

Track IDs are in the format `<track_number>-<speaker_id>`, where `track_number`
identifies a track and `speaker_id` identifies the speaker. This allows multiple
tracks to belong to the same speaker.

The `speaker_id` is used to look up a human-readable label in `config.toml`.
"""

from dossier.utils.config import get_config


def speaker_id(track_id: str) -> str:
    """Extract the speaker ID from a track ID."""
    return track_id.partition("-")[2] or track_id


def speaker_labels() -> dict[str, str]:
    """Return configured human-readable speaker labels."""
    return get_config().speakers.labels


def speaker_label(track_id: str) -> str:
    """Return the human-readable label for a track ID."""
    label_key = speaker_id(track_id)
    return speaker_labels().get(label_key, label_key)


def labelize_tracks(tracks: list[str]) -> dict[str, str]:
    """Map track IDs to human-readable speaker labels."""
    return {track: speaker_label(track) for track in tracks}
