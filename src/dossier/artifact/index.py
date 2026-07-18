"""Index artifact for tracking all recordings/workspaces."""

import secrets
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field
from slugify import slugify

from dossier.artifact.base import VersionedModel
from dossier.artifact.recording import RecordingArtifact
from dossier.utils.dir import RECORDINGS_DIR


class WorkspaceEntry(BaseModel):
    """Indexed recording workspace."""

    id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)


class Index(VersionedModel):
    """
    Index artifact for tracking all recordings/workspaces.

    Stored as:

        index.json
    """

    recordings: list[WorkspaceEntry] = Field(default_factory=list)
    aliases: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def rebuild_alias_index(self) -> None:
        """Rebuild the alias lookup table from recordings."""
        self.aliases.clear()

        for entry in self.recordings:
            self.aliases[entry.id] = entry.id  # Map ID to itself
            for alias in entry.aliases:
                if alias in self.aliases:
                    raise ValueError(f"Duplicate alias '{alias}' found in index.")
                self.aliases[alias] = entry.id

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return RECORDINGS_DIR / "index.json"

    @classmethod
    def load(cls) -> "Index":
        """Load the index artifact from disk."""
        from dossier.utils.storage import load_file

        path = RECORDINGS_DIR / "index.json"

        return load_file(path, cls)


class IndexController:
    """Controller for managing the index artifact."""

    index: Index

    def __init__(self) -> None:
        self.index: Index = self.get_index()

    def get_index(self) -> Index:
        """Retrieve the index artifact, initializing it if it doesn't exist."""
        if not (RECORDINGS_DIR / "index.json").exists():
            print("Initializing Transcriber CLI Index..")
            self.index = Index()
            self.save_index()
        else:
            self.index = Index.load()
        return self.index

    def save_index(self) -> None:
        """Save the index artifact to disk."""
        from dossier.utils.storage import save_file

        save_file(self.index)

    def _get_recording(self, id_or_alias: str) -> WorkspaceEntry | None:
        """Retrieve a recording entry by ID or alias."""
        recording_id = self.index.aliases.get(id_or_alias)
        if recording_id is None:
            return None
        for entry in self.index.recordings:
            if entry.id == recording_id:
                return entry
        return None

    def get_recording(self, id_or_alias: str) -> RecordingArtifact:
        """Retrieve the recording artifact by ID or alias."""
        recording_entry = self._get_recording(id_or_alias)
        if recording_entry is None:
            raise ValueError(f"Recording '{id_or_alias}' not found in index.")
        return RecordingArtifact.load(recording_entry.id)

    def add_recording(self, recording_id: str, name: str, aliases: list[str] | None = None) -> None:
        """Add a new recording to the index."""
        from slugify import slugify

        slug_aliases = [slugify(alias, word_boundary=True, max_length=40) for alias in (aliases or [])]

        if aliases and any(alias != slug for alias, slug in zip(aliases, slug_aliases, strict=True)):
            print("warning: Some aliases have been slugified to ensure they are valid and safe for use as identifiers.")

        if any(entry.id == recording_id for entry in self.index.recordings):
            raise ValueError(f"Recording ID '{recording_id}' already exists in the index.")

        new_entry = WorkspaceEntry(id=recording_id, display_name=name, aliases=slug_aliases)
        self.index.recordings.append(new_entry)
        self.index.rebuild_alias_index()
        self.save_index()

    def remove_recording(self, recording_id: str) -> None:
        """Remove a recording from the index."""
        self.index.recordings = [entry for entry in self.index.recordings if entry.id != recording_id]
        self.index.rebuild_alias_index()
        self.save_index()


def generate_recording_id(name: str) -> str:
    """Generate a unique ID for the recording, still human readable and relevant to the workspace name."""
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    slug = slugify(name, word_boundary=True, max_length=40)
    suffix = secrets.token_hex(3)

    return f"{slug}_{date}_{suffix}"
