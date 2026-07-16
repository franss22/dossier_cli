"""Index artifact for tracking all recordings/workspaces."""

from pydantic import BaseModel, Field

from dossier.artifact.base import Artifact
from pathlib import Path
from dossier.utils.dir import STORAGE_ROOT


class WorkspaceEntry(BaseModel):
    """Indexed recording workspace."""

    id: str
    aliases: list[str] = Field(default_factory=list)


class IndexArtifact(Artifact):
    """
    Index artifact for tracking all recordings/workspaces.

    Stored as:

        index.json
    """

    recordings: list[WorkspaceEntry] = Field(default_factory=list)
    aliases: dict[str, str] = Field(default_factory=dict)

    def rebuild_alias_index(self) -> None:
        """Rebuild the alias lookup table from recordings."""
        self.aliases.clear()

        for entry in self.recordings:
            for alias in entry.aliases:
                if alias in self.aliases:
                    raise ValueError(f"Duplicate alias '{alias}' found in index.")
                self.aliases[alias] = entry.id

    def storage_path(self) -> Path:
        """Exact storage location for this artifact."""
        return STORAGE_ROOT / "index.json"
