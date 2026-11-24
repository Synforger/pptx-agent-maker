"""Building one deck from a manifest.

3 通りの作り方を **1 本の経路**に合わせる ― 型で組んだ頁はいったん pptx に焼き、
テンプレートの複製も過去デッキからの輸入も同じ「頁を持ってくる」操作にする。経路が 2 本あると、
どちらの順序が本当かが分からなくなる。
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path

from .._common.page_label import manifest_page_label
from ..layout import types
from ..layout.parts.page import PageFullError
from ..layout.tokens import Theme, ThemeError, allowed_pairs, theme_from
from ..project.files.manifest import Entry, Manifest, ManifestError
from ..project.files.workspace import Workspace, WorkspaceError
from ..review.take.fold import keep_safe
from ..review.ledger import remember, touched_by_hand
from ._internal.look import merged
from ._internal.under import under_of
from ..write import add_page, aspect, new_deck, save
from . import Deck, Slide


class HandEditedError(RuntimeError):
    """The deck on disk was edited by a person; building would erase that."""


class OpenInPowerPointError(RuntimeError):
    """The deck is open in PowerPoint; writing it now loses either this build or the person's edits."""


def _open_in_powerpoint(deck: Path) -> Path | None:
    """The lock file PowerPoint keeps beside `deck` while it is open (= None when it is not open).

    ⚠ **開いたままの PowerPoint は、次に保存した時か閉じた時に、自分が持っている中身で file を書き戻す。**
    開いている最中に書き出すと、書き出した版か人の直しのどちらかが消える。手で直した後に閉じた資料は
    `touched_by_hand` が止めるが、開いている最中はまだ file に何も書かれていないので、そちらでは分からない。
    印の名前は `~$` + 資料の名前 (= 長い名前では頭の 2 字が `~$` に置き換わる)。
    """
    for name in ("~$" + deck.name, "~$" + deck.name[2:]):
        lock = deck.with_name(name)
        if lock.exists():
            return lock
    return None


def theme_of(workspace: Workspace, manifest: Manifest) -> Theme:
    """The look this manifest's declared pages are built in: the specimen's, with the project's laid over.

    見本からはもう 1 つ読む ― 型の頁が乗るレイアウトが持つ物 (= 題の枠と、印字される物。`_internal/under.py`)。

    検査で通すと決めた字と地の色の組 (= `[checks] contrast_allowed`) も渡す ― 組む側は、その組の字の色を
    寄せない (= `Palette.words_on`。検査と同じ読み方で、読む所は `allowed_pairs` 1 つ)。

    字の大きさは、この資料が `use` で名指した使い方のもの (= 書いていなければ案件のもの)。頁が自分の
    使い方を名指す時は、ここで返した見た目から選び直す (= `Theme.using`)。
    """
    specimen = workspace.specimen(manifest.specimen).resolve()
    if not specimen.is_file():
        raise ManifestError(f"specimen not found: {specimen}")
    try:
        under = under_of(specimen, (workspace.look or {}).get("layout_of_page"))
    except ValueError as reason:
        raise ManifestError(f"workspace.toml: {reason}") from reason
    look = theme_from(merged(specimen, workspace.look))
    allowed = allowed_pairs((workspace.settings or {}).get("checks") or {})
    look = replace(look, under=under, palette=replace(look.palette, allowed=allowed))
    try:
        return look.using(manifest.use or None)
    except ThemeError as reason:
        where = manifest.source.name if manifest.source else "the manifest"
        raise ManifestError(f"{where}: {reason}") from reason


def build(workspace: Workspace, manifest: Manifest) -> Path:
    """Assemble the deck the manifest describes and return where it landed."""
    theme = theme_of(workspace, manifest)
    specimen = workspace.specimen(manifest.specimen).resolve()

    destination = workspace.out(manifest.out)
    lock = _open_in_powerpoint(destination)
    if lock is not None:
        raise OpenInPowerPointError(
            f"{destination.name} is open in PowerPoint (its lock file {lock.name} is beside it) — writing it now "
            "would lose either this build or the edits made in PowerPoint. Ask for it to be saved and closed, "
            "fold the edits in (`review`), then build again."
        )
    if touched_by_hand(destination):
        shelved = keep_safe(destination)
        raise HandEditedError(
            f"{destination.name} was edited by hand since it was built — a copy is at "
            f"{shelved}. Fold those changes in (`review`) or delete the file, then build again."
        )

    with tempfile.TemporaryDirectory() as scratch:
        declared = _bake_declared(workspace, manifest, Path(scratch), theme)
        with Deck.open(specimen, destination) as deck:
            for index, entry in enumerate(manifest.entries, start=1):
                page = _place(deck, workspace, entry, declared, index, theme.under.layout)
                _swap(page, workspace, manifest, entry, index)
                for old, new in entry.replace:
                    page.replace(old, new)
    remember(destination)
    return destination


def _place(deck: Deck, workspace: Workspace, entry: Entry, declared: dict[int, int],
           index: int, layout: str) -> Slide:
    if entry.kind == "copy":
        return deck.copy(entry.page)
    if entry.kind == "import":
        source = (workspace.root / entry.deck).resolve()
        if not source.is_file():
            raise ManifestError(f"{manifest_page_label(index)}: deck to import from not found: {source}")
        return deck.bring(source, entry.page)
    return deck.bring(declared["path"], declared[index], relayout=layout)


def _swap(page: Slide, workspace: Workspace, manifest: Manifest, entry: Entry,
          index: int) -> None:
    """New pictures and table cells into a copied or imported page."""
    try:
        if "pictures" in entry.data:
            page.swap_pictures([workspace.asset(str(name), within=manifest.assets)
                                for name in entry.data["pictures"]])
        if "tables" in entry.data:
            page.swap_tables(entry.data["tables"])
    except (ValueError, WorkspaceError) as reason:
        raise ManifestError(f"{manifest_page_label(index)}: {reason}") from reason


def _bake_declared(workspace: Workspace, manifest: Manifest, scratch: Path,
                   theme: Theme) -> dict:
    """Render every declared page into one deck, remembering which page each became.

    宣言頁が 1 つも無ければ焼かない (= 空のデッキを作らない)。
    """
    declared = [(index, entry) for index, entry in enumerate(manifest.entries, start=1)
                if entry.kind == "declare"]
    if not declared:
        return {}

    deck = new_deck(theme)
    where: dict = {}
    for position, (index, entry) in enumerate(declared, start=1):
        page = declared_page(workspace, manifest, entry, index, theme)
        # 頁は自分の使い方の見た目で書く (= 表の行の高さや箱の余白も、組んだ時と同じ大きさから出る)
        add_page(deck, page.build(), page.theme)
        where[index] = position
    where["path"] = save(deck, scratch / "declared.pptx")
    return where


def declared_page(workspace: Workspace, manifest: Manifest, entry: Entry, index: int,
                   theme: Theme):
    """Build a declared page, saying which page of the manifest went wrong."""
    def asset(name: str):
        return workspace.asset(name, within=manifest.assets)

    # 収まらない頁も「どの頁か」を付けて返す (= 型が縮めずに止めた理由は、頁を直す人が読む)
    try:
        return types.build(entry.data, asset, aspect, theme)
    except (ValueError, KeyError, WorkspaceError, PageFullError) as reason:
        raise ManifestError(f"{manifest_page_label(index)}: {reason}") from reason
