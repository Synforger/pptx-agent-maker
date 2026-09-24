"""Things that end up printed on top of each other.

見るのは**描かれる物どうし** (= `ink.py`)。枠どうしで見ると、画面では離れている物が
重なりとして上がる ― 前の世代はそれで上がったものがほとんど誤検出で、最後は
「自作の頁だけ見る」という逃げ方で黙らせていた。実デッキでは**題がロゴに掛かる**と
報告されたが、題の文字はロゴのだいぶ手前で終わっていた。

2 種類を見る:

* **下敷きとの重なり** ― その頁が乗るレイアウトとマスター (= ロゴ・頁番号・飾り)。
  ⚠ **頁ごとに別のレイアウトに乗る**ので、レイアウトは頁から辿る
* **文字どうしの重なり** ― 同じ頁の文字が別の文字に掛かる。塗りや絵との重なりは
  見ない (= 図の背景として敷くのは正常)
"""

from __future__ import annotations

from pathlib import Path

from ..finding import Finding
from ..ink import draws_anything, has_body, ink_of
from ..slide import read

NAME = "overlap"

#: これ以下の食い込みは見逃す (= 0.05 inch。印刷でも画面でも判別できない量)。
#: 目に見えない食い込みで台帳が埋まると、本当の重なりが埋もれる。
TOLERANCE = 45720


def _over(a, b, tolerance: int) -> bool:
    """Do the two rectangles share more than `tolerance` in both directions?"""
    return (min(a[2], b[2]) - max(a[0], b[0]) > tolerance
            and min(a[3], b[3]) - max(a[1], b[1]) > tolerance)


def _words(shape) -> str:
    return " ".join(shape.texts()).strip()


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    """`tolerance` は案件が緩められる (= 既定で足りないテンプレートのために)。"""
    tolerance = int((config or {}).get("overlap_tolerance", TOLERANCE))
    findings: list[Finding] = []

    for page in read(deck):
        mine = [(shape, mark) for shape in page.shapes() for mark in ink_of(shape)]
        under = [(shape, mark) for shape in page.beneath if draws_anything(shape)
                 for mark in ink_of(shape)]

        for shape, mark in mine:
            for beneath, below in under:
                if _over(mark, below, tolerance):
                    findings.append(Finding(
                        NAME, page.number, (_words(shape) or shape.kind)[:60],
                        f"sits on what the layout already puts there "
                        f"({(_words(beneath) or beneath.kind)[:30]!r})"))
                    break

        words = [(shape, mark) for shape, mark in mine if not has_body(shape)]
        for index, (shape, mark) in enumerate(words):
            for other, elsewhere in words[index + 1:]:
                if shape is other:
                    continue
                if _over(mark, elsewhere, tolerance):
                    findings.append(Finding(
                        NAME, page.number, (_words(shape) or shape.kind)[:60],
                        f"prints over {(_words(other) or other.kind)[:30]!r}"))
                    break

    return findings
