"""Taking a hand-edited deck back into the manifest.

流れは 3 手 ― **退避する / 見比べる / manifest に書ける形で出す**。ここは見比べて出すまでで、
manifest への取り込みは `apply.py` (= `review --apply`)。人が触るのは PowerPoint で、取り込むのは
エージェントの仕事。
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .compare import Change, changes
from .ledger import touched_by_hand

EDITS = "_edits"


def keep_safe(deck: Path) -> Path | None:
    """Copy a hand-edited deck somewhere the next build cannot reach it."""
    deck = Path(deck)
    if not touched_by_hand(deck):
        return None
    shelf = deck.parent / EDITS
    shelf.mkdir(parents=True, exist_ok=True)
    stamped = shelf / f"{deck.stem}-{datetime.now():%Y%m%d-%H%M%S}{deck.suffix}"
    shutil.copy2(deck, stamped)
    return stamped


def fold(built: Path, edited: Path) -> list[Change]:
    """What the person changed, ready to be written into the manifest."""
    return changes(Path(built), Path(edited))


def as_manifest_entries(found: list[Change]) -> str:
    """The changes as replacement pairs, to paste into the manifest.

    ⚠ 出すのは**置換できるものだけ** (= 文言の差し替え)。頁の追加や削除、動かした位置も含めて
    取り込むのは `review --apply`。
    """
    lines = ["# paste into the page's `replace` list:"]
    replaceable = [c for c in found if c.kind == "changed"]
    if not replaceable:
        lines.append("#   (nothing that is a plain text swap)")
    for change in replaceable:
        lines.append(f'  ["{change.before}", "{change.after}"],   # page {change.page}')
    other = [c for c in found if c.kind != "changed"]
    if other:
        lines.append("")
        lines.append("# not a text swap — `review --apply` takes these in as the edited page:")
        lines.extend(f"#   {c.render()}" for c in other)
    return "\n".join(lines)
