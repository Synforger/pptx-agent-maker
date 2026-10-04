"""Pointing at a deck project that lives outside this repository."""

from .commands.scaffold import create
from .files.workspace import Workspace, WorkspaceError

__all__ = ["Workspace", "WorkspaceError", "create"]
