"""Building one deck from a manifest.

3 通りの作り方を **1 本の経路**に合わせる ― 宣言層で組んだ頁はいったん pptx に焼き、
型見本の複製も過去デッキからの輸入も同じ「頁を持ってくる」操作にする。経路が 2 本あると、
どちらの順序が本当かが分からなくなる。
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

from ..project.manifest import Entry, Manifest, ManifestError
from ..project.workspace import Workspace
from ..review.fold import keep_safe
from ..review.ledger import remember, touched_by_hand
from ..write import add_page, new_deck, save
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

    with tempfile.TemporaryDirectory() as scratch:
        declared = _bake_declared(workspace, manifest, Path(scratch))
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
    return deck.bring(declared["path"], declared[index])


def _bake_declared(workspace: Workspace, manifest: Manifest, scratch: Path) -> dict:
    """Render every declared page into one deck, remembering which page each became.

    宣言頁が 1 つも無ければ焼かない (= 空のデッキを作らない)。
    """
    declared = [(index, entry) for index, entry in enumerate(manifest.entries, start=1)
                if entry.kind == "declare"]
    if not declared:
        return {}

    deck = new_deck()
    where: dict = {}
    for position, (index, entry) in enumerate(declared, start=1):
        page = _load_page(workspace, entry.module)
        add_page(deck, page.build())
        where[index] = position
    where["path"] = save(deck, scratch / "declared.pptx")
    return where


def _load_page(workspace: Workspace, module: str):
    """Run a page recipe from the project's own pages/ folder."""
    source = workspace.pages / f"{module}.py"
    if not source.is_file():
        raise ManifestError(f"page recipe not found: {source}")

    spec = importlib.util.spec_from_file_location(f"project_page_{module}", source)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    if not hasattr(loaded, "build"):
        raise ManifestError(f"{source} has no build(workspace) function")
    return loaded.build(workspace)
