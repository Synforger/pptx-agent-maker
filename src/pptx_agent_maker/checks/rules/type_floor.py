"""Type smaller than anyone can read from a seat.

⚠ 見るのは**実際に文字を持つ run** だけ (= 空の run の大きさは誰も読まない)。

下限は資料の使い方が決める (= `type_floor`)。自分の使い方を名指した頁は、その使い方の下限で見る
(= `type_floor_of`: 頁の番号 → 下限。映す資料の途中に挟んだ、読ませる大きさの 1 枚)。
"""

from __future__ import annotations

from pathlib import Path

from ..base.finding import Finding
from ..base.slide import read

NAME = "type_floor"
DEFAULT_FLOOR = 10.0


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    deck_floor = float((config or {}).get("type_floor", DEFAULT_FLOOR))
    of_page = (config or {}).get("type_floor_of") or {}
    findings: list[Finding] = []
    for page in read(deck):
        floor = float(of_page.get(page.number, deck_floor))
        for shape in page.shapes():
            for size in shape.type_sizes():
                if size < floor:
                    label = (shape.texts() or [""])[0][:40]
                    findings.append(Finding(
                        NAME, page.number, f"{size:g}pt {label!r}",
                        f"below the {floor:g}pt floor — unreadable from a seat"))
    return findings
