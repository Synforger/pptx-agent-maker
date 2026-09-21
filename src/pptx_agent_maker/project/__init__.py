"""Pointing at a deck project that lives outside this repository."""

from .scaffold import create
from .workspace import Workspace, WorkspaceError

__all__ = ["Workspace", "WorkspaceError", "create"]
