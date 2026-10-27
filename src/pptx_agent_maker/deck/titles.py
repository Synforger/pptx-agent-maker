"""The titles of a deck in order: what it says when nothing else is read.

題は結論の文で、**題だけを順に読むと話が通る**のが良いデッキ (= 横の論理)。頁を 1 枚ずつ直して
いると、並びとしての話は見えなくなる。ここは題だけを抜き出して並べる ― 読むのは人。
"""

from __future__ import annotations

from .._common.page_label import page_number
from .._common.slide import first_slide_number, read
from ..project.files.manifest import Manifest
from ..project.files.workspace import Workspace


def titles(workspace: Workspace, manifest: Manifest) -> list[str]:
    """One line per page: its number, the small words above its title if any, and the title.

    宣言で組む頁は manifest から読む (= まだ焼いていなくても出る)。複製と輸入の頁は、差し替えた後の
    題が焼いた deck にしか無いので、そこから読む。

    ⚠ **焼いた deck の数え始めが 1 でなければ、頁の位置に刷られる番号を並べる** (= 人が言う番号で話せる)。
    焼いていなければ刷られる番号は決まらないので、位置だけを出す。
    """
    built = workspace.out(manifest.out)
    pages = read(built) if built.is_file() else []
    first_number = first_slide_number(built) if built.is_file() else 1
    labels = [page_number(number, first_number) for number in range(1, len(manifest.entries) + 1)]
    width = max([3, *map(len, labels)])
    lines = []
    for number, entry in enumerate(manifest.entries, start=1):
        kicker = ""
        if entry.kind == "declare":
            kicker, title = str(entry.data.get("kicker", "")), str(entry.data.get("title", ""))
            # 差し替えは文字の並びの全体が一致した時だけ効く (= 焼くときと同じ決まり)
            for old, new in entry.replace:
                kicker, title = (new if kicker == old else kicker), (new if title == old else title)
        elif number <= len(pages):
            title = pages[number - 1].headline()
        else:
            title = f"(a page to {entry.kind} — build the deck to read its title)"
        lines.append(f"{labels[number - 1]:>{width}}  " + (f"[{kicker}]  " if kicker else "") + title)
    return lines
