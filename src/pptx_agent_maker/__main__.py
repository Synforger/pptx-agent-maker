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
    # ⚠ repo から動かしたときだけ在る path。入れたツールでは preview は別の package。
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
    # ⚠ **テンプレートは焼いた成果ではない。**マニフェストが指している pptx を一覧から外す。
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
    started.add_argument("--specimen", default=None, metavar="PPTX",
                         help="the .pptx this project takes its look from, or a folder\nholding specimen.pptx and a workspace.toml to go with it")

    promoted = sub.add_parser("promote", help="keep pages written the same way as one recipe")
    promoted.add_argument("path", help="the project folder")
    promoted.add_argument("name", help="the recipe's name")
    promoted.add_argument("pages", nargs="+", metavar="MANIFEST:PAGE",
                          help="two or more pages of one shape, e.g. w1:5 w2:7")

    lifted = sub.add_parser("lift", help="lift recipes and pages into a template, with the project taken out")
    lifted.add_argument("path", help="the project folder")
    lifted.add_argument("template", help="the template folder (= specimen.pptx and its workspace.toml)")
    lifted.add_argument("--recipe", action="append", default=[], metavar="NAME")
    lifted.add_argument("--page", action="append", default=[], metavar="DECK:PAGE")
    lifted.add_argument("--replace", action="append", default=[], metavar="OLD=NEW",
                        help="a project word and what stands in for it")
    lifted.add_argument("--keep", action="append", default=[], metavar="WORDS",
                        help="words that stay as they are (everything else becomes <文言 N>)")

    rounded = sub.add_parser("round", help="start the next round from the one before")
    rounded.add_argument("path", help="the project folder")
    rounded.add_argument("name", help="the new round, e.g. w2")
    rounded.add_argument("--from", dest="previous", required=True, metavar="MANIFEST",
                         help="the round to start from, e.g. w1")

    listed = sub.add_parser("types", help="list the page types, the keys each reads, and the project's recipes")
    listed.add_argument("path", help="the project folder")

    refreshed = sub.add_parser("refresh", help="hand an existing project the tasks and skill of this toolkit")
    refreshed.add_argument("path", help="the project folder")

    shown = sub.add_parser("show", help="print where a project keeps its things")
    shown.add_argument("path")
    shown.add_argument("page", nargs="?", metavar="DECK:PAGE",
                       help="list one page's pictures and tables in the order a manifest fills them")

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
    reviewed.add_argument("--apply", action="store_true",
                          help="take the edit into the manifest: words and pictures where the "
                               "manifest can say them, the edited page itself where it cannot")
    reviewed.add_argument("--against", default=None,
                          help="the machine-built deck to compare with (default: the last shelved copy)")

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            where = create(args.path, name=args.name, specimen=args.specimen)
            print(f"created {where}")
            # ⚠ **建てただけでは次に何を打つか分からない。**案件の folder には task の口が
            # 入っているので、ツールの名前ではなくそちらを案内する。
            print(f"  next: cd {where} && task build -- example")
            return 0

        workspace = Workspace.load(args.path)
        if args.command == "show" and args.page:
            from .deck.swap import SwapError, describe

            deck, _, number = args.page.rpartition(":")
            if not deck or not number.isdigit():
                print(f"error: {args.page!r} is not DECK:PAGE (e.g. w1.pptx:12)", file=sys.stderr)
                return 1
            try:
                print(describe(_deck_path(workspace, deck), int(number)))
            except (SwapError, OSError) as error:
                print(f"error: {error}", file=sys.stderr)
                return 1
            return 0

        if args.command == "show":
            print(f"root       {workspace.root}")
            for name in FOLDERS:
                folder = getattr(workspace, name)
                print(f"  {name:<9} {folder}{'' if folder.exists() else '   (missing)'}")
            return 0

        if args.command == "promote":
            from .project.recipes import RecipeError, promote

            targets = []
            for spec in args.pages:
                manifest, _, number = spec.rpartition(":")
                if not manifest or not number.isdigit():
                    print(f"error: {spec!r} is not MANIFEST:PAGE (e.g. w1:5)", file=sys.stderr)
                    return 1
                targets.append((manifest, int(number)))
            try:
                written = promote(workspace.root, args.name, targets)
            except RecipeError as error:
                print(f"error: {error}", file=sys.stderr)
                return 1
            print(f"promoted {len(targets)} pages to recipe {args.name!r}")
            for path in written:
                print(f"  wrote {path.name}")
            return 0

        if args.command == "refresh":
            from .project.refresh import refresh

            changed, kept = refresh(workspace.root)
            if not changed:
                print("already up to date with this toolkit")
                return 0
            for relative in changed:
                print(f"  refreshed {relative}")
            if kept is not None:
                print(f"the versions it had are kept at {kept.relative_to(workspace.root)}")
            return 0

        if args.command == "types":
            from .layout.types import describe
            from .project.manifest import CARRIED_KEYS
            from .project.recipes import HOLE
            from .project.recipes import load as load_recipes

            print(describe())
            print(f"copy / import pages read: {', '.join(sorted(CARRIED_KEYS - {'kind'}))} "
                  "(copy has no deck)")
            print("recipe pages read: recipe, fill, why, replace, and what the recipe leaves open")
            print("any page may carry: why (= a one-line note, 200 characters, no dates)")
            recipes = load_recipes(workspace.root)
            print(f"recipes in this project ({len(recipes)}):")
            for name, recipe in recipes.items():
                holes = sorted({h for v in recipe.values() if isinstance(v, str)
                                for h in HOLE.findall(v)})
                fixed = ", ".join(k for k in recipe if k != "type")
                print(f"  {name:<12} type: {recipe['type']:<12} fixes: {fixed or '—'}"
                      f"{'  fill: ' + ', '.join(holes) if holes else ''}")
            return 0

        if args.command == "round":
            from .project.round import RoundError, start

            try:
                written = start(workspace.root, args.name, args.previous)
            except RoundError as error:
                print(f"error: {error}", file=sys.stderr)
                return 1
            print(f"started {written.name} from {args.previous} "
                  f"(= its pages as they were; assets/{written.stem}/ is empty — "
                  "put this round's material there)")
            return 0

        if args.command == "lift":
            from .project.lift import LiftError, lift

            pages, replace = [], []
            for spec in args.page:
                deck, _, number = spec.rpartition(":")
                if not deck or not number.isdigit():
                    print(f"error: {spec!r} is not DECK:PAGE (e.g. w1.pptx:3)", file=sys.stderr)
                    return 1
                pages.append((deck, int(number)))
            for spec in args.replace:
                old, sep, new = spec.partition("=")
                if not sep:
                    print(f"error: {spec!r} is not OLD=NEW", file=sys.stderr)
                    return 1
                replace.append((old, new))
            try:
                done = lift(workspace.root, args.template, recipes=args.recipe,
                            pages=pages, replace=replace, keep=args.keep)
            except LiftError as error:
                print(f"error: {error}", file=sys.stderr)
                return 1
            for name in done.recipes:
                print(f"lifted recipe {name!r} into {args.template}/recipes.toml")
            for position in done.pages:
                print(f"lifted a page as specimen page {position} (pictures grey, alt text dropped)")
            for label, placed in done.words.items():
                print(f"  {label} — what went in (= kept with --keep / --replace, the rest stands in):")
                for original, now in placed:
                    print(f"    {now}" if now == original else f"    {now}  <- {original}")
            if done.stale:
                print(f"stale_words now include: {', '.join(done.stale)}")
            print(f"the template as it was is kept at {done.kept_at} "
                  "(= copy those files back to undo)")
            return 0

        if args.command == "preview":
            return _preview(workspace, args.port, args.no_open)

        from .checks import report, run_all

        if args.command == "review" and args.apply:
            from .review.apply import ApplyError, apply

            try:
                done = apply(workspace, args.deck)
            except (ApplyError, ManifestError) as error:
                print(f"error: {error}", file=sys.stderr)
                return 1
            print(f"took {args.deck} into {done.manifest.name} (the edited deck is kept at "
                  f"{done.kept_at.relative_to(workspace.root)})")
            for note in done.notes:
                print(f"  {note}")
            print("  checked: built again, every page reads and shows as it was edited")
            return 0

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
    except (WorkspaceError, ManifestError, FileExistsError, FileNotFoundError,
            ValueError, IndexError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
