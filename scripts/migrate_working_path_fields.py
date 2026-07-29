"""Migrate legacy artifact path fields to working_path under STORAGE_ROOT.

This script updates only known artifact files:
- recording.json: audio.tracks[*].file -> working_path
- chunks/*/manifest.json: tracks[*].chunks[*].path_from_root -> working_path

Default mode is dry-run. Use --write to apply changes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dossier.utils.dir import STORAGE_ROOT


def migrate_recording_json(path: Path) -> tuple[bool, int]:
    """Migrate legacy track file fields in recording.json.

    Returns:
        changed: Whether the file content was changed.
        edits: Number of field replacements made.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    edits = 0

    tracks = data.get("audio", {}).get("tracks", [])
    if not isinstance(tracks, list):
        return False, 0

    for track in tracks:
        if not isinstance(track, dict):
            continue

        if "working_path" not in track and "file" in track:
            track["working_path"] = track["file"]
            track.pop("file", None)
            edits += 1

    if edits == 0:
        return False, 0

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True, edits


def migrate_chunk_manifest_json(path: Path) -> tuple[bool, int]:
    """Migrate legacy chunk path fields in chunk manifest.

    Returns:
        changed: Whether the file content was changed.
        edits: Number of field replacements made.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    edits = 0

    tracks = data.get("tracks", [])
    if not isinstance(tracks, list):
        return False, 0

    for track in tracks:
        if not isinstance(track, dict):
            continue

        chunks = track.get("chunks", [])
        if not isinstance(chunks, list):
            continue

        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue

            if "working_path" not in chunk and "path_from_root" in chunk:
                chunk["working_path"] = chunk["path_from_root"]
                chunk.pop("path_from_root", None)
                edits += 1

    if edits == 0:
        return False, 0

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True, edits


def collect_targets(storage_root: Path) -> list[tuple[Path, str]]:
    """Collect known artifact JSON files that may need migration."""
    targets: list[tuple[Path, str]] = []

    recordings_dir = storage_root / "recordings"
    if not recordings_dir.exists():
        return targets

    for workspace in recordings_dir.iterdir():
        if not workspace.is_dir():
            continue

        recording_json = workspace / "recording.json"
        if recording_json.exists():
            targets.append((recording_json, "recording"))

        chunks_dir = workspace / "chunks"
        if chunks_dir.exists():
            for run_dir in chunks_dir.iterdir():
                manifest = run_dir / "manifest.json"
                if run_dir.is_dir() and manifest.exists():
                    targets.append((manifest, "chunk_manifest"))

    return targets


def run(storage_root: Path, write: bool) -> int:
    """Run migration and print a summary.

    Returns:
        Exit code.
    """
    if not storage_root.exists():
        print(f"error: storage root does not exist: {storage_root}")
        return 2

    targets = collect_targets(storage_root)

    files_changed = 0
    total_edits = 0

    for path, kind in targets:
        original = path.read_text(encoding="utf-8")

        if kind == "recording":
            changed, edits = migrate_recording_json(path)
        else:
            changed, edits = migrate_chunk_manifest_json(path)

        if not changed:
            continue

        files_changed += 1
        total_edits += edits

        if not write:
            # Revert modifications in dry-run mode.
            path.write_text(original, encoding="utf-8")

        mode_label = "WRITE" if write else "DRY-RUN"
        print(f"[{mode_label}] {path} (edits={edits})")

    if write:
        print(f"done: migrated {files_changed} file(s), {total_edits} edit(s)")
    else:
        print(f"dry-run: would migrate {files_changed} file(s), {total_edits} edit(s)")

    return 0


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Migrate legacy artifact path fields to working_path")
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=STORAGE_ROOT,
        help="Path to storage root (defaults to dossier.utils.dir.STORAGE_ROOT)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply changes in place. Without this flag, script runs in dry-run mode.",
    )
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()
    return run(args.storage_root, write=args.write)


if __name__ == "__main__":
    raise SystemExit(main())
