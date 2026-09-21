"""`python3 -m pptx_agent_maker <command>` — start a project, look at it, build a deck."""

from __future__ import annotations

import argparse
import sys

from .project import Workspace, WorkspaceError, create
from .project.manifest import Manifest, ManifestError

FOLDERS = ("base", "manifests", "pages", "assets", "output")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pptx_agent_maker", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    started = sub.add_parser("init", help="lay down a new deck project, outside this repo")
    started.add_argument("path")
    started.add_argument("--name", default=None)

    shown = sub.add_parser("show", help="print where a project keeps its things")
    shown.add_argument("path")

    built = sub.add_parser("build", help="build a deck from one of the project's manifests")
    built.add_argument("path", help="the project folder")
    built.add_argument("manifest", help="a manifest name, with or without .toml")

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            where = create(args.path, name=args.name)
            print(f"created {where}")
            return 0

        workspace = Workspace.load(args.path)
        if args.command == "show":
            print(f"root       {workspace.root}")
            for name in FOLDERS:
                folder = getattr(workspace, name)
                print(f"  {name:<9} {folder}{'' if folder.exists() else '   (missing)'}")
            return 0

        from .deck.build import build

        manifest = Manifest.load(workspace.manifest(args.manifest))
        built_deck = build(workspace, manifest)
        print(f"built {built_deck} ({len(manifest.entries)} pages)")
        return 0
    except (WorkspaceError, ManifestError, FileExistsError, IndexError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
