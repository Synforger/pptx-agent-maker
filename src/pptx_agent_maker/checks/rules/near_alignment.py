"""Siblings that were meant to line up and miss by a hair.

宣言で組む頁は同じ枠から割るので揃う。**ずれるのは複製と輸入**で、手で並べた箱が 0.5 mm だけ
上下にずれたまま来る。1 mm 以上離れた端は、わざとずらした物とみなして言わない。

⚠ **比べるのは「揃うはずの組」だけ。**端どうしを全部比べると、帯の下に引いた線、箱の中の文字の
余白、大きさの違う印を中心で揃えた物まで当たる (= 見本の案件を宣言で組んだだけで 455 組当たった)。
揃うはずの組 = 同じ大きさの兄弟 ― 横に並び (= 左右に重ならず、上下に重なる) 高さが同じなら上端、
縦に積まれ (= 上下に重ならず、左右に重なる) 幅が同じなら左端。線のように細い物 (= 1 mm 未満) は外す。

⚠ **塗った箱の中の物と、頁の地に置いた物は兄弟ではない。**目次の右のカードの中の 1 行と、左の一覧の
1 行が、たまたま同じ高さで横に並んで当たった (= 列ごとに別の割り方で置いた物)。片方だけが箱 (= 字を
持たず、地を塗った図形) の中に在る組は比べない。どちらも箱の中に在る組 (= 並んだカード 2 枚の見出し) と、
どちらも地に在る組は、今までどおり比べる。

閾値は 1 mm 未満のずれ (= 案件で外すなら `[checks] near_alignment = false`)。

⚠ **所見に出す桁で 0 になるずれは、揃っている。**絵が並ぶ頁で「0.00 mm ずれている」が 5 件出た (= EMU の
端数で数 EMU 違うだけ)。直す人が数字を見て直せないずれは言わない ― 下限は表示の桁 (`PLACES`) から決まる。
"""

from __future__ import annotations

import re
from pathlib import Path

from ..base.finding import Finding
from ..base.slide import Shape, read

NAME = "near_alignment"
#: 1 mm = 36000 EMU (= これ未満のずれを「揃え損ね」、同じ大きさの差もこれ未満を「同じ」とみなす)
MM = 36000
#: 所見に出すずれの桁 (= mm の小数)。この桁で 0 になるずれは揃っているとみなす
PLACES = 2


def _shared(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


def _miss(a: Shape, b: Shape) -> tuple[str, int] | None:
    """Which edge two siblings miss by, and by how much (EMU), or None."""
    if (not _shared(a.left, a.right, b.left, b.right) and _shared(a.top, a.bottom, b.top, b.bottom)
            and abs(a.height - b.height) < MM):
        return "top", abs(a.top - b.top)
    if (not _shared(a.top, a.bottom, b.top, b.bottom) and _shared(a.left, a.right, b.left, b.right)
            and abs(a.width - b.width) < MM):
        return "left", abs(a.left - b.left)
    return None


#: 図形の地の指定 (= 枠の線の中の `noFill` は地ではない)
_SHAPE_PROPERTIES = re.compile(r"<p:spPr\b.*?</p:spPr>", re.S)
_LINE = re.compile(r"<a:ln\b.*?(?:</a:ln>|/>)", re.S)


def _ground(shape: Shape) -> bool:
    """A box: a shape with no words whose ground is painted (= a card, a band)."""
    if shape.kind != "sp" or shape.texts():
        return False
    found = _SHAPE_PROPERTIES.search(shape.xml)
    return not found or "<a:noFill/>" not in _LINE.sub("", found.group(0))


def _boxed(shape: Shape, boxes: list[Shape]) -> bool:
    """Whether the shape sits inside a box other than itself."""
    return any(box is not shape and box.left <= shape.left and box.top <= shape.top
               and shape.right <= box.right and shape.bottom <= box.bottom for box in boxes)


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    if (config or {}).get(NAME, True) is False:
        return []
    findings: list[Finding] = []
    for page in read(deck):
        shapes = [shape for shape in page.shapes() if shape.width >= MM and shape.height >= MM]
        boxes = [shape for shape in shapes if _ground(shape)]
        boxed = {id(shape): _boxed(shape, boxes) for shape in shapes}
        for index, one in enumerate(shapes):
            for other in shapes[index + 1:]:
                if boxed[id(one)] != boxed[id(other)]:
                    continue
                miss = _miss(one, other)
                if miss and round(miss[1] / MM, PLACES) > 0 and miss[1] < MM:
                    edge, by = miss
                    findings.append(Finding(
                        NAME, page.number,
                        f"{(one.texts() or [one.kind])[0][:30]!r} and {(other.texts() or [other.kind])[0][:30]!r}",
                        f"their {edge} edges miss by {by / MM:.{PLACES}f} mm — line them up"))
    return findings
