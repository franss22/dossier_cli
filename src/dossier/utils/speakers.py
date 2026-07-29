"""Utility functions for working with speakers in transcripts.

Track IDs are in the format `<track_number>-<speaker_id>`, where `track_number`
identifies a track and `speaker_id` identifies the speaker. This allows multiple
tracks to belong to the same speaker.

The `speaker_id` is used to look up a human-readable label in `SPEAKERS`.
"""

SPEAKERS = {
    "b1rdest": "Diego (Mishima)",
    "cfspr": "Coni (May)",
    "exrider": "Luciano (Moriarty)",
    "emi22z": "Emi (GM)",
    "quemares": "Menares (Morgan)",
    "kleinmetallicis": "Taco (Mastiff)",
}


def speaker_label(track_id: str) -> str:
    """Return the human-readable label for a track ID."""
    speaker_id = track_id.partition("-")[2] or track_id
    return SPEAKERS.get(speaker_id, speaker_id)


def labelize_tracks(tracks: list[str]) -> dict[str, str]:
    """Map track IDs to human-readable speaker labels."""
    return {track: speaker_label(track) for track in tracks}
