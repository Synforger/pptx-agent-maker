"""Building one deck from a manifest.

3 通りの作り方を **1 本の経路**に合わせる ― 型で組んだ頁はいったん pptx に焼き、
型見本の複製も過去デッキからの輸入も同じ「頁を持ってくる」操作にする。経路が 2 本あると、
どちらの順序が本当かが分からなくなる。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ..layout import types
from ..layout.tokens import Theme, theme_from
from ..project.manifest import Entry, Manifest, ManifestError
from ..project.workspace import Workspace
from ..review.fold import keep_safe
from ..review.ledger import remember, touched_by_hand
from .look import merged
from ..write import add_page, aspect, new_deck, save
from . import Deck, Slide


class HandEditedError(RuntimeError):
    """The deck on disk was edited by a person; building would erase that."""


def build(workspace: Workspace, manifest: Manifest) -> Path:
    """Assemble the deck the manifest describes and return where it landed."""
    specimen = (workspace.root / manifest.specimen).resolve()
    if not specimen.is_file():
        raise ManifestError(f"specimen not found: {specimen}")

    destination = workspace.out(manifest.out)
    if touched_by_hand(destination):
        shelved = keep_safe(destination)
        raise HandEditedError(
            f"{destination.name} was edited by hand since it was built — a copy is at "
            f"{shelved}. Fold those changes in (`review`) or delete the file, then build again."
        )

    theme = theme_from(merged(specimen, workspace.look))

    with tempfile.TemporaryDirectory() as scratch:
        declared = _bake_declared(workspace, manifest, Path(scratch), theme)
        with Deck.open(specimen, destination) as deck:
            for index, entry in enumerate(manifest.entries, start=1):
                page = _place(deck, workspace, entry, declared, index)
                for old, new in entry.replace:
                    page.replace(old, new)
    remember(destination)
    return destination


def _place(deck: Deck, workspace: Workspace, entry: Entry, declared: dict[int, int],
           index: int) -> Slide:
    if entry.kind == "copy":
        return deck.copy(entry.page)
    if entry.kind == "import":
        source = (workspace.root / entry.deck).resolve()
        if not source.is_file():
            raise ManifestError(f"page {index}: deck to import from not found: {source}")
        return deck.bring(source, entry.page)
    return deck.bring(declared["path"], declared[index], relayout=True)


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
        page = _declared_page(workspace, manifest, entry, index, theme)
        add_page(deck, page.build(), theme)
        where[index] = position
    where["path"] = save(deck, scratch / "declared.pptx")
    return where


def _declared_page(workspace: Workspace, manifest: Manifest, entry: Entry, index: int,
                   theme: Theme):
    """Build a declared page, saying which page of the manifest went wrong."""
    def asset(name: str):
        return workspace.asset(name, within=manifest.assets)

    try:
        return types.build(entry.data, asset, aspect, theme)
    except (ValueError, KeyError) as reason:
        raise ManifestError(f"page {index}: {reason}") from reason
