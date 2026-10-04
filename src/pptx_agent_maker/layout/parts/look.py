"""How a box, a bar or an arrowhead is painted, and the grounds it may sit on."""

from __future__ import annotations

from dataclasses import dataclass

from ..base.tokens import ROLES


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
