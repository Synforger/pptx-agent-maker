"""`python3 -m pptx_agent_maker <command>` — start a project, look at it, build a deck."""

from __future__ import annotations

import argparse
import hashlib
import json
import importlib.util
import os
import sys
import threading
import time
from pathlib import Path

from .project import Workspace, WorkspaceError, create
from .project.files.manifest import Manifest, ManifestError

FOLDERS = ("assets",)


PREVIEW = Path(__file__).resolve().parents[2] / "preview" / "src"
#: 常駐のプレビューが道具の file を見直す間隔 (= 秒)。変わった指紋を 2 回続けて見てから起動し直すので、
#: checkout が書き換わっている途中では起動しない
RESTART_POLL_S = 5.0


def _use_checkout_preview() -> None:
    """Put the preview that sits in this checkout on the import path (= only a checkout has one)."""
    if PREVIEW.is_dir() and str(PREVIEW) not in sys.path:
        sys.path.insert(0, str(PREVIEW))


def _preview_package():
    """The live preview's modules, from this checkout or from the installed package."""
    _use_checkout_preview()
    import pptx_live_preview.__main__ as entry
    import pptx_live_preview.state as state
    return entry, state


def _skip_of(folder: Path) -> set[str]:
    """A project's own template, left out of its deck list."""
    return _specimens(Workspace.load(folder))


def _fingerprint() -> str:
    """The toolkit's own source and its preview's as they stand on disk (= moves when the checkout moves)."""
    _use_checkout_preview()
    found = importlib.util.find_spec("pptx_live_preview")
    packages = [Path(__file__).resolve().parent]
    if found is not None and found.origin:
        packages.append(Path(found.origin).resolve().parent)
    seen = hashlib.sha1()
    for package in packages:
        for path in sorted(package.rglob("*.py")):
            stat = path.stat()
            seen.update(f"{package.name}/{path.relative_to(package)}:{stat.st_mtime_ns}:{stat.st_size}\n".encode())
    return seen.hexdigest()


def _restart_when_changed(started: str) -> None:
    """Start this process again with the same arguments once the toolkit on disk has changed and settled.

    ⚠ **常駐は起動した時の道具のまま走り続ける。**checkout が進んでも、走っている process は古い道具で
    案件を読み、新しい欄を書いた案件を断る。人が画面を開くまで誰も気づかないので、自分で起動し直す
    (= 同じ process の番号のまま入れ替わる。launchd の下でも端末から起動した時でも同じに効く)。
    """
    seen = started
    while True:
        time.sleep(RESTART_POLL_S)
        now = _fingerprint()
        if now != started and now == seen:
            print("the toolkit changed on disk; starting the preview again with it", file=sys.stderr, flush=True)
            os.execv(sys.executable, sys.orig_argv)
        seen = now


def _watch_the_toolkit(started: str) -> None:
    """Keep an eye on the toolkit's files for the life of the preview."""
    threading.Thread(target=_restart_when_changed, args=(started,), daemon=True).start()


def _offers(places: dict, started: str, since: str):
    """What the places file offers, each unreadable project told whether a restart would help.

    ⚠ **常駐は起動した時の道具のまま走り続ける。**repo から入れた道具は、checkout が進んでも
    走っている process の中身は変わらない。新しい欄を書いた案件はその道具で読めず、画面には
    理由だけが出る ― 道具の file が起動の後に変わっていれば、それも理由に添える。
    """
    from .project.files.places import discover

    found = discover(places, _skip_of)
    if any(offer.problem for offer in found.values()) and _fingerprint() != started:
        note = (f" — this preview still runs the toolkit as it was at {since}, and the toolkit "
                "has changed since; restart the preview to read the project with the current one")
        found = {name: offer._replace(problem=offer.problem + note) if offer.problem else offer
                 for name, offer in found.items()}
    return found


#: 見せる物が 1 つも無い時の画面の帯 (= 案件を作れば、画面が一覧を取りに来た時に出る)
NOTHING_YET = ("nothing to show yet — no deck project and no folder the places name exists; "
               "a project shows here as soon as it is made")


def _places_of_this_machine() -> tuple[dict, str | None]:
    """The machine's places file as it stands now, and why it could not be read (= None when it could).

    ⚠ **常駐は、置き場の設定が無い・読めない機械でも起きている。**断って終わると launchd が起こし直しては
    落ち、落ちた log だけが積もる (= 案件の無い機械で 1 日に数千回)。読めない理由は画面の帯に出し、
    file を置くか直せば、次に画面が一覧を取りに来た時に読む。
    """
    from .project.files.places import load

    try:
        return load(), None
    except (ValueError, OSError) as error:  # PlacesError と、toml として読めない file
        return {}, str(error)


def _preview_places(read, port: int, no_open: bool) -> int:
    """Everything a places file offers behind one page, one of them looked at.

    1 案件の起動と同じ画面を使い、上の欄で選ぶ。描くのは選んだ物だけ。一覧は画面が
    取りに来るたびに探し直す (= 常駐のまま、新しい案件が欄に出る)。`read` は置き場と、読めなかった
    理由を返す (= 探し直すたびに呼ぶ)。見せる物が 1 つも無くても起動し、空の画面に理由を出して待つ。
    """
    try:
        entry, state = _preview_package()
    except ImportError as error:  # pragma: no cover - depends on the environment
        print(f"error: the live preview is not available ({error})", file=sys.stderr)
        return 1
    started, since = _fingerprint(), time.strftime("%Y-%m-%d %H:%M")
    unread: list[str | None] = [None]  # 最後に探した時、置き場を読めなかった理由

    def offers() -> dict:
        places, unread[0] = read()
        return _offers(places, started, since)

    found = offers()
    if found:
        print(f"{len(found)} to choose from: {', '.join(sorted(found))}")
    else:
        print(f"{unread[0] or NOTHING_YET} (waiting)", file=sys.stderr)
    first = {}
    for name, offer in found.items():
        first[name] = state.DeckSet(offer.folder, skip=offer.skip)
        first[name].set_problem(offer.problem, offer.skip)
    board = state.Switchboard(first, discover=offers, waiting=lambda: unread[0] or NOTHING_YET)
    _watch_the_toolkit(started)
    return entry.serve(board, port, no_open)


def _preview(workspace, port: int, no_open: bool) -> int:
    """Hand the project's folder to the live preview, which lives in this repo.

    焼く工程と見る工程を同じ画面に置くのが、この repo を 1 つにした理由。
    ビルドがデッキを書き換えると、プレビューがそのまま焼き直す。焼いたデッキは
    マニフェストの隣に在るので、見るのは案件の folder そのもの。
    """
    # ⚠ repo から動かしたときだけ在る path。入れたツールでは、プレビューはツールと一緒に入っている。
    _use_checkout_preview()
    try:
        from pptx_live_preview.__main__ import main as preview_main
    except ImportError as error:  # pragma: no cover - depends on the environment
        hint = (f"       run: pip install -e {PREVIEW.parent}" if PREVIEW.is_dir()
                else "       the live preview is installed with the toolkit; install the toolkit "
                     "again from its checkout (pipx install --force --editable <checkout>)")
        print(f"error: the live preview is not available ({error}).\n{hint}", file=sys.stderr)
        return 1

    argv = [str(workspace.root), "--port", str(port)]
    if no_open:
        argv.append("--no-open")
    # ⚠ **テンプレートは焼いた成果ではない。**マニフェストが指している pptx を一覧から外す。
    for name in _specimens(workspace):
        argv += ["--skip", name]
    _watch_the_toolkit(_fingerprint())
    return preview_main(argv)


def _specimens(workspace) -> set[str]:
    """The files the project's manifests grow decks from (= not decks themselves)."""
    from .project.files.manifest import Manifest, ManifestError

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


def _checks(workspace, manifest=None, theme=None) -> dict:
    """What the project asks of the checks, with the type floor of the deck's use filled in.

    文字の下限は資料の使い方が決める (= 映す資料は 14pt、読ませる資料は 10pt)。`theme` はその資料の見た目
    (= manifest が使い方を名指していれば、その使い方)。自分の使い方を名指した頁は、その使い方の下限で
    見る。案件が `[checks] type_floor` を書いていれば、どの頁でもそちらが勝つ。
    """
    from .layout.tokens import theme_from

    asked = workspace.settings.get("checks", {})
    config = {"type_floor": (theme or theme_from(workspace.look)).type.minimum, **asked}
    if manifest is not None and theme is not None and "type_floor" not in asked:
        config["type_floor_of"] = {
            number: theme.using(entry.data.get("use")).type.minimum
            for number, entry in enumerate(manifest.entries, start=1)
            if entry.kind == "declare" and entry.data.get("use")}
    template = _template_media(workspace, manifest)
    if template:
        config["template_media"] = template
    return config


def _template_media(workspace, manifest=None) -> set[str]:
    """What the project's templates carry as pictures (= left out of the picture checks).

    この資料の manifest が分かればその雛形、分からなければ案件の manifest が使う雛形の全部。
    """
    from .checks._internal.picture import media_digests
    from .project.files.manifest import Manifest, ManifestError

    if manifest is not None:
        specimens = {manifest.specimen}
    else:
        specimens = set()
        for path in workspace.manifests():
            try:
                specimens.add(Manifest.load(path).specimen)
            except (ManifestError, OSError):
                continue  # 読めないマニフェストは build が言う
    found: set[str] = set()
    for specimen in specimens:
        path = workspace.specimen(specimen)
        if path.is_file():
            found |= media_digests(path)
    return found


def _manifest_of(workspace, deck: Path):
    """The manifest a built deck came from (= the one whose `out` is this file), or None."""
    from .project.files.manifest import Manifest, ManifestError

    for path in workspace.manifests():
        try:
            manifest = Manifest.load(path)
        except (ManifestError, OSError):
            continue  # 読めないマニフェストは build が言う
        if workspace.out(manifest.out).resolve() == deck.resolve():
            return manifest
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pptx_agent_maker", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    started = sub.add_parser("init", help="lay down a new deck project, outside this repo")
    started.add_argument("path")
    started.add_argument("--name", default=None)
    started.add_argument("--specimen", default=None, metavar="PPTX",
                         help="the .pptx this project takes its look from, or a folder\nholding specimen.pptx and what goes with it (workspace.toml,\nexample.toml, recipes.toml)")

    promoted = sub.add_parser("promote", help="keep pages written the same way as one recipe")
    promoted.add_argument("path", help="the project folder")
    promoted.add_argument("name", help="the recipe's name")
    promoted.add_argument("pages", nargs="+", metavar="MANIFEST:PAGE",
                          help="two or more pages of one shape, e.g. w1:5 w2:7")

    lifted = sub.add_parser("lift", help="lift recipes and pages into a template, with the project taken out")
    lifted.add_argument("path", help="the project folder")
    lifted.add_argument("template", help="the template folder (= specimen.pptx and its workspace.toml)")
    lifted.add_argument("--recipe", action="append", default=[], metavar="NAME")
    lifted.add_argument("--part", action="append", default=[], metavar="NAME")
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

    titled = sub.add_parser("titles", help="print every page's title in order, to read the story the deck tells")
    titled.add_argument("path", help="the project folder")
    titled.add_argument("manifest", help="a manifest name, with or without .toml")

    framed = sub.add_parser("frames", help="print, as JSON, the frame each declared picture is given (= draw it that size)")
    framed.add_argument("path", help="the project folder")
    framed.add_argument("manifest", help="a manifest name, with or without .toml")

    checked = sub.add_parser("check", help="check a deck that is already built")
    checked.add_argument("path", help="the project folder")
    checked.add_argument("deck", help="a built deck in the project, or a path")

    watched = sub.add_parser("preview", help="watch the project's decks in a browser")
    watched.add_argument("path", nargs="?", default=None,
                         help="the project folder, or a folder holding several projects "
                              "(= left out: what the places file offers)")
    watched.add_argument("--places", default=None, metavar="FILE",
                         help="the file listing what to offer (default: config/pptx-agent-maker/preview.toml under "
                              "$AGENT_PLATFORM_ROOT when set, else ~/.config/pptx-agent-maker/preview.toml)")
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

    compared = sub.add_parser("compare", help="compare two versions of a deck page by page, by the pixels that differ")
    compared.add_argument("before", help="the deck as it was")
    compared.add_argument("after", help="the deck as it is now")

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            where = create(args.path, name=args.name, specimen=args.specimen)
            print(f"created {where}")
            # ⚠ **建てただけでは次に何を打つか分からない。**案件の folder には task の口が
            # 入っているので、ツールの名前ではなくそちらを案内する。
            print(f"  next: cd {where} && task build -- example")
            return 0

        if args.command == "preview" and (
                args.path is None or args.places or not (Path(args.path) / "workspace.toml").is_file()):
            _use_checkout_preview()  # places が根の置き場をプレビューの部品から引く
            from .project.files.places import PlacesError, load

            if args.path is not None and not args.places:
                places = {"search": [{"path": str(Path(args.path).expanduser().resolve())}]}
            elif args.places:  # 打った人が名指した file は、読めなければその場で言う
                try:
                    places = load(args.places)
                except PlacesError as error:
                    print(f"error: {error}", file=sys.stderr)
                    return 1
            else:
                return _preview_places(_places_of_this_machine, args.port, args.no_open)
            return _preview_places(lambda: (places, None), args.port, args.no_open)

        if args.command == "compare":
            _use_checkout_preview()  # 頁を絵に描く部品は、プレビューの物と同じ
            from pptx_live_preview.render import RenderError

            from ._common.slide import first_slide_number
            from .compare import changed_count, compare_decks, fonts_named, missing_fonts, render_font_note, render_report

            before, after = Path(args.before).expanduser(), Path(args.after).expanduser()
            try:
                differences = compare_decks(before, after)
            except (RenderError, FileNotFoundError) as error:
                # 終わりの code 1 は「違う頁がある」の印なので、比べられなかった回は 2 で分ける
                print(f"error: {error}", file=sys.stderr)
                return 2
            # 資料の書体がこの機械に無いと、同じ資料でも字のある頁の画素が揺れる。数は変えず、知らせるだけ
            note = render_font_note(missing_fonts(fonts_named(before) | fonts_named(after)))
            if note:
                print(note, file=sys.stderr)
            print(render_report(differences, first_slide_number(after)))
            return 1 if changed_count(differences) else 0

        workspace = Workspace.load(args.path)
        if args.command == "show" and args.page:
            from .deck.pages.swap import SwapError, describe

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
            from .project.files.recipes import RecipeError, promote

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
            from .project.commands.refresh import refresh

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
            from .project.files.manifest import CARRIED_KEYS
            from .project.files.recipes import HOLE
            from .project.files.recipes import load as load_recipes

            print(describe())
            from .layout.parts.look import TONES
            from .layout.tokens import theme_from

            named = theme_from(workspace.look).ground_names()
            print(f"tone (= the ground of a box, a bar, a lane): {', '.join(TONES)}"
                  + (f"; named in this project's [theme.grounds]: {', '.join(named)}" if named else ""))
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
            from .project.files.recipes import load_parts

            parts = load_parts(workspace.root)
            print(f"parts in this project ({len(parts)}; a compose cell writes part = \"<name>\" and fill):")
            for name, part in parts.items():
                holes = sorted(set(HOLE.findall(repr(part))))
                print(f"  {name:<16} holds: {', '.join(part)}{'  fill: ' + ', '.join(holes) if holes else ''}")
            return 0

        if args.command == "round":
            from .project.commands.round import RoundError, start

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
            from .project.commands.lift import LiftError, lift

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
                            pages=pages, replace=replace, keep=args.keep, parts=args.part)
            except LiftError as error:
                print(f"error: {error}", file=sys.stderr)
                return 1
            for name in done.recipes:
                print(f"lifted recipe {name!r} into {args.template}/recipes.toml")
            for name in done.parts:
                print(f"lifted part {name!r} into {args.template}/recipes.toml")
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

        if args.command == "titles":
            from .deck.titles import titles

            for line in titles(workspace, Manifest.load(workspace.manifest(args.manifest))):
                print(line)
            return 0

        if args.command == "frames":
            from .deck.frames import frames

            print(json.dumps(frames(workspace, Manifest.load(workspace.manifest(args.manifest))), indent=2))
            return 0

        from ._common.slide import first_slide_number
        from .checks import report, run_all, run_built

        if args.command == "review" and args.apply:
            from .review.take.apply import ApplyError, apply

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
            first_number = first_slide_number(edited)
            for change in found:
                print(change.render(first_number))
            print()
            print(as_manifest_entries(found, first_number))
            return 0

        if args.command == "check":
            target = _deck_path(workspace, args.deck)
            # 案件の manifest から焼いた資料なら、焼いた時と同じ下限で見る (= 資料と頁の使い方)
            from .deck.build import theme_of

            source = _manifest_of(workspace, target)
            findings = run_all(target, _checks(workspace, source, theme_of(workspace, source) if source else None))
            print(report(findings, first_number=first_slide_number(target)))
            return 1 if findings else 0

        from .deck.build import build, theme_of

        manifest = Manifest.load(workspace.manifest(args.manifest))
        built_deck = build(workspace, manifest)
        first_number = first_slide_number(built_deck)
        counted = f"; the page numbers printed start at {first_number}" if first_number != 1 else ""
        print(f"built {built_deck} ({len(manifest.entries)} pages{counted})")
        # 案件に写した手順書と task が、このツールの物と違えば言う (= 古い手順で組んだまま気づかない)
        from .project.commands.refresh import stale

        if differ := stale(workspace.root):
            print(f"note: {len(differ)} of the toolkit's files in this project differ from this toolkit's "
                  f"(the deck skill, the Taskfile) — `task refresh` takes them, keeping the ones it replaces")
        if args.skip_checks:
            return 0
        # 焼いた deck を読み直す検査と、manifest を読む検査を、1 つの報告に並べる
        theme = theme_of(workspace, manifest)
        findings = run_built(built_deck, manifest, theme, _checks(workspace, manifest, theme))
        print(report(findings, declared=True, first_number=first_number))
        return 1 if findings else 0
    except (WorkspaceError, ManifestError, FileExistsError, FileNotFoundError,
            ValueError, IndexError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
