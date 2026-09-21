"""Lining up the words of two decks, page by page.

⚠ **番人の差分を照合の根拠にしない** ― 先頭 30 字で切れる差分を信じたせいで、頁後半の
削除が「一致」と出た。ここは全文を取り出して突き合わせる。

⚠ **単純に順番で比べない** ― run の本数が食い違った時点から後ろが全部偽の差分になる。
difflib で対応を取る。
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

from ..checks.slide import read


@dataclass(frozen=True)
class Change:
    """One difference between the built deck and the edited one."""

    page: int
    before: str
    after: str

    @property
    def kind(self) -> str:
        if not self.before:
            return "added"
        if not self.after:
            return "removed"
        return "changed"

    def render(self) -> str:
        if self.kind == "added":
            return f"page {self.page}: + {self.after!r}"
        if self.kind == "removed":
            return f"page {self.page}: - {self.before!r}"
        return f"page {self.page}: {self.before!r} -> {self.after!r}"


def changes(built: Path, edited: Path) -> list[Change]:
    """Every run that differs, page by page."""
    ours, theirs = read(Path(built)), read(Path(edited))
    found: list[Change] = []
    for number, (mine, yours) in enumerate(zip(ours, theirs), start=1):
        found.extend(_page_changes(number, mine.texts(), yours.texts()))
    for extra in theirs[len(ours):]:
        found.append(Change(extra.number, "", f"(a whole page: {' / '.join(extra.texts()[:2])})"))
    for gone in ours[len(theirs):]:
        found.append(Change(gone.number, f"(a whole page: {' / '.join(gone.texts()[:2])})", ""))
    return found


def _page_changes(page: int, before: list[str], after: list[str]) -> list[Change]:
    found: list[Change] = []
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            for old, new in zip(before[i1:i2], after[j1:j2]):
                found.append(Change(page, old, new))
            for old in before[i1 + (j2 - j1):i2]:
                found.append(Change(page, old, ""))
            for new in after[j1 + (i2 - i1):j2]:
                found.append(Change(page, "", new))
        elif tag == "delete":
            found.extend(Change(page, old, "") for old in before[i1:i2])
        else:
            found.extend(Change(page, "", new) for new in after[j1:j2])
    return [c for c in found if c.before.strip() or c.after.strip()]
