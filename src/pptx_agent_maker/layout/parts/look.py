"""How a box, a bar or an arrowhead is painted, and the grounds it may sit on."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..base.tokens import ROLES


@dataclass(frozen=True)
class Style:
    """The four looks anything shaped like a box may be written with: read once, carried as one.

    箱・棒・矢羽根のどれもが、この 1 組を同じ意味で持つ。部品ごとに 1 つずつ持たせていた間は、
    1 つ足すたびに部品の数だけ書き足すことになった。
    """

    #: 地の色の役 (= `TONES` か、案件が名前を付けた地)。空は「書かれていない」で、置く側が決める
    tone: str = "box"
    #: 名前の前に置く絵の file と、その縦横比 (= 無ければ None)
    icon: tuple[Path, float] | None = None
    #: 点線の枠 (= 在れば / 内容未定)
    tentative: bool = False
    #: 太い枠 (= クリティカルパス、目を集めたい 1 つ)
    strong: bool = False


@dataclass(frozen=True)
class Look:
    """How a box, a bar or an arrowhead is painted: one answer for all three."""

    fill: str
    ink: str
    outline: str
    dashed: bool = False
    heavy: bool = False


#: 箱と棒の地に使える色の役。`box` / `band` / `tint` は薄い地で意味を持たない (= 3 者までを
#: 色で分けられる)。`accent` は目を集めたい物、`good` / `bad` は**読み** (= 良い / 悪い) を
#: 示す物にだけ使う
TONES = ROLES


#: 薄い地。紙とも列の地とも近いので、地を濃くした色の枠を持つ (= `Palette.edge`)
LIGHT = TONES[:3]
