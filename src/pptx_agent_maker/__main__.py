"""`python3 -m pptx_agent_maker <command>` — start a project, look at it, build a deck."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .project import Workspace, WorkspaceError, create
from .project.manifest import Manifest, ManifestError

FOLDERS = ("assets",)


PREVIEW = Path(__file__).resolve().parents[2] / "preview" / "src"


def _preview(workspace, port: int, no_open: bool) -> int:
    """Hand the project's folder to the live preview, which lives in this repo.

    焼く工程と見る工程を同じ画面に置くのが、この repo を 1 つにした理由。
    ビルドがデッキを書き換えると、プレビューがそのまま焼き直す。焼いたデッキは
    マニフェストの隣に在るので、見るのは案件の folder そのもの。
    """
    # ⚠ repo から動かしたときだけ在る path。入れた道具では preview は別の package。
    if PREVIEW.is_dir() and str(PREVIEW) not in sys.path:
        sys.path.insert(0, str(PREVIEW))
    try:
        from pptx_live_preview.__main__ import main as preview_main
    except ImportError as error:  # pragma: no cover - depends on the environment
        hint = (f"       run: pip install -e {PREVIEW.parent}" if PREVIEW.is_dir()
                else "       the live preview is a separate package; install it "
                     "beside the toolkit")
        print(f"error: the live preview is not available ({error}).\n{hint}", file=sys.stderr)
        return 1

    argv = [str(workspace.root), "--port", str(port)]
    if no_open:
        argv.append("--no-open")
    # ⚠ **型見本は焼いた成果ではない。**マニフェストが指している pptx を一覧から外す。
    for name in _specimens(workspace):
        argv += ["--skip", name]
    return preview_main(argv)


def _specimens(workspace) -> set[str]:
    """The files the project's manifests grow decks from (= not decks themselves)."""
    from .project.manifest import Manifest, ManifestError

    found = set()
    for manifest in workspace.manifests():
        try:
            found.add(Path(Manifest.load(manifest).specimen).stem)
        except (ManifestError, OSError):
            continue  # 読めないマニフェストは build が言う。ここは一覧を作るだけ
    return found


def _deck_path(workspace, name: str) -> Path:
    """A deck by name: a path as given, or one beside its manifest."""
    target = Path(name)
    if not target.is_absolute():
        target = workspace.root / name
    if not target.suffix:
        target = target.with_suffix(".pptx")
    return target


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
    built.add_argument("--skip-checks", action="store_true", help="build without checking")

    checked = sub.add_parser("check", help="check a deck that is already built")
    checked.add_argument("path", help="the project folder")
    checked.add_argument("deck", help="a built deck in the project, or a path")

    watched = sub.add_parser("preview", help="watch the project's decks in a browser")
    watched.add_argument("path", help="the project folder")
    watched.add_argument("--port", type=int, default=0, help="0 picks a free port")
    watched.add_argument("--no-open", action="store_true", help="do not launch a browser")

    reviewed = sub.add_parser("review", help="see what a person changed in a built deck")
    reviewed.add_argument("path", help="the project folder")
    reviewed.add_argument("deck", help="the hand-edited deck in the project")
    reviewed.add_argument("--full", action="store_true",
                          help="print the diff of every changed part, not just its name")
    reviewed.add_argument("--raw", action="store_true",
                          help="with --full, keep PowerPoint's own churn instead of folding it")
    reviewed.add_argument("--context", type=int, default=0,
                          help="lines of context around each change (default: 0)")
    reviewed.add_argument("--against", default=None,
                          help="the machine-built deck to compare with (default: the last shelved copy)")

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            where = create(args.path, name=args.name)
            print(f"created {where}")
            # ⚠ **建てただけでは次に何を打つか分からない。**案件の folder には task の口が
            # 入っているので、道具の名前ではなくそちらを案内する。
            print(f"  next: cd {where} && task build -- example")
            return 0

        workspace = Workspace.load(args.path)
        if args.command == "show":
            print(f"root       {workspace.root}")
            for name in FOLDERS:
                folder = getattr(workspace, name)
                print(f"  {name:<9} {folder}{'' if folder.exists() else '   (missing)'}")
            return 0

        if args.command == "preview":
            return _preview(workspace, args.port, args.no_open)

        from .checks import report, run_all

        if args.command == "review":
            from .review import as_manifest_entries, changes, keep_safe, last_machine_build

            edited = _deck_path(workspace, args.deck)
            # ⚠ **比べる相手を先に確かめてから退避する。**先に控えを取っていた間は、
            # 相手が無くて失敗した回でも控えだけが増え、その控えを渡すとまた控えが
            # できて入れ子になった (= 失敗した操作が跡を残さないのが筋)。
            reference = Path(args.against) if args.against else last_machine_build(edited)
            if reference is None:
                print(f"error: nothing to compare {edited.name} against. The toolkit keeps "
                      "one copy of what it last built beside the deck; there is none here.\n"
                      "       Pass the deck the toolkit built (not a copy of it), or name a "
                      "reference with --against.", file=sys.stderr)
                return 1
            shelved = keep_safe(edited)
            if shelved:
                print(f"kept a copy at {shelved}")
            from .review import compare_parts, render_parts

            # 落とさない層を先に出す (= 読み取る項目を 1 つずつ足す形は、
            # 足していない項目を黙って落とす)。既定は一覧だけ、--full で中身まで。
            inventory = compare_parts(reference, edited)
            print(render_parts(inventory, full=args.full, context=args.context,
                               fold_churn=not args.raw))
            print()
            found = changes(reference, edited)
            for change in found:
                print(change.render())
            print()
            print(as_manifest_entries(found))
            return 0

        if args.command == "check":
            target = _deck_path(workspace, args.deck)
            findings = run_all(target, workspace.settings.get("checks", {}))
            print(report(findings))
            return 1 if findings else 0

        from .deck.build import build

        manifest = Manifest.load(workspace.manifest(args.manifest))
        built_deck = build(workspace, manifest)
        print(f"built {built_deck} ({len(manifest.entries)} pages)")
        if args.skip_checks:
            return 0
        findings = run_all(built_deck, workspace.settings.get("checks", {}))
        print(report(findings))
        return 1 if findings else 0
    except (WorkspaceError, ManifestError, FileExistsError, IndexError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
