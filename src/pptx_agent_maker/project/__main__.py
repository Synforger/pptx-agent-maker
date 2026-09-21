"""`python3 -m pptx_agent_maker.project init <path>` — lay down a deck project."""

from __future__ import annotations

import argparse
import sys

from .scaffold import create
from .workspace import Workspace, WorkspaceError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or inspect a deck project.")
    sub = parser.add_subparsers(dest="command", required=True)

    started = sub.add_parser("init", help="lay down a new project folder")
    started.add_argument("path", help="where the project goes (outside this repo)")
    started.add_argument("--name", default=None, help="project name (default: the folder name)")

    shown = sub.add_parser("show", help="print where a project keeps its things")
    shown.add_argument("path", help="the project folder, or its workspace.toml")

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            where = create(args.path, name=args.name)
            print(f"created {where}")
            print(f"  edit {where / 'workspace.toml'} if the layout differs")
            return 0
        workspace = Workspace.load(args.path)
        print(f"root       {workspace.root}")
        for name in ("base", "manifests", "pages", "assets", "output"):
            folder = getattr(workspace, name)
            print(f"  {name:<9} {folder}{'' if folder.exists() else '   (missing)'}")
        return 0
    except (WorkspaceError, FileExistsError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
