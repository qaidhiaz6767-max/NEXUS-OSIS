"""Trusted startup configuration; model input never chooses a database or grants."""

from dataclasses import dataclass
from pathlib import Path
from contextlib import ExitStack
from .storage import Store

from .permissions import CAPABILITIES


@dataclass(frozen=True)
class Workspace:
    id: str
    label: str
    domain: str


WORKSPACES = (
    Workspace("osis", "OSIS", "school"),
    Workspace("personal", "Personal", "personal"),
    Workspace("academic", "Academic", "school"),
    Workspace("research", "Research", "personal"),
    Workspace("coding", "Development", "personal"),
    Workspace("finance", "Finance", "personal"),
    Workspace("atlas", "ATLAS", "company"),
)


class WorkspaceRegistry:
    """One local trusted operator. Grants are supplied by host code, never HTTP/AI.

    Separate files isolate normal application access; this is not an OS sandbox
    against someone who can read the local account's files.
    """

    def __init__(
        self, legacy_db: Path, workspace_root: Path, grants=None, *, runtime_locks=False
    ):
        self._runtime_locks = runtime_locks
        self._leases = ExitStack()
        self._leased = set()
        self.workspaces = {w.id: w for w in WORKSPACES}
        self.grants = (
            {w.id: CAPABILITIES for w in WORKSPACES}
            if grants is None
            else {k: frozenset(v) for k, v in grants.items()}
        )
        if any(
            k not in self.workspaces or not v <= CAPABILITIES
            for k, v in self.grants.items()
        ):
            raise ValueError("Invalid workspace grants")
        self.paths = {
            w.id: Path(workspace_root) / w.id / "nexus.sqlite3" for w in WORKSPACES
        }
        self.paths["osis"] = Path(legacy_db)
        resolved = [p.resolve() for p in self.paths.values()]
        if len(set(resolved)) != len(resolved):
            raise ValueError("Workspace database paths must be distinct")

    def list(self):
        return [
            dict(
                id=w.id,
                label=w.label,
                domain=w.domain,
                capabilities=sorted(self.grants[w.id]),
            )
            for w in WORKSPACES
            if "read" in self.grants.get(w.id, ())
        ]

    def store(self, workspace_id: str) -> Store:
        if workspace_id not in self.workspaces:
            raise ValueError("Unknown workspace")
        grants = self.grants.get(workspace_id, frozenset())
        if "read" not in grants:
            raise PermissionError("Workspace access denied")
        if self._runtime_locks and workspace_id not in self._leased:
            from .backup import database_lease

            self._leases.enter_context(database_lease(self.paths[workspace_id]))
            self._leased.add(workspace_id)
        return Store(
            self.paths[workspace_id], workspace_id=workspace_id, capabilities=grants
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._leases.close()
        self._leased.clear()
