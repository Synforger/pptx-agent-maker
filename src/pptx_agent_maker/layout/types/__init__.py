"""The finite set of page shapes a deck may use.

**型を用意して「使ってください」にすると、使われない。**前の世代では頁の縦位置を
いくつか名前で持っていたが、頁は隣に自分の値を書き、名前のある位置のすぐ横に
名前のない値が積み上がった。読み手には、0.3mm のずれが重なった揺れとして届く。

ここでは頁が**型を選ぶことしかできない**。座標を書く口も、並びを変える口も無い。

頁の並びは 1 つしかない。書かなかった帯は取られないだけで、順序は動かない:

    題 → 条件の帯 → カード → **本体** → 表 → 読み方 → 結論の帯 → 出所

型が決めるのは**本体に何をどう置くか**だけで、カード・表・読み方・要点はどの型でも
添えられる。既に組まれたデッキ群を数えると、頁の中身は「絵が 1 枚か / 並ぶか / 無いか」
と「表と文を添えるか」でほとんど尽きていた ― 本体の形を型に、それ以外を付属にすると、
型は 7 つで足りた。8 つめの `timeline` は、絵で描いて貼ると文字が絵に焼き込まれて人が
直せなくなる頁 (= 期間 × レーンの計画) のために足した。9 つめの `roadmap` も同じ理由で、
到達点までの道のりを矢羽根の図形のまま組む。10 個めの `chart` も同じ ― 絵で貼ったグラフは、渡した
先で誰も数字を直せない。

    figure          絵 1 枚が本体
    figures         絵を横に並べる (= 条件ちがいの比較)
    figure_grid     絵を格子に並べる (= 対象 × 条件のような 2 軸)
    flow            段が左から右へ流れる (= 各段にノード、段の下に分かったこと)
    roadmap         到達点までの段が矢羽根で左から右へ (= 各段の下に、その段で渡す物)
    timeline        期間が左から右、レーンが上から下 (= レーンの中に棒と印)
    chart           数字から描くグラフ (= 棒・縦棒・折れ線・積み上げ・滝グラフ。数字は deck の中)
    cards           カードの並びが本体 (= 今週の計画、まとめ)
    board           表 1 枚が本体 (= 毎週積み上げる早見表)
    agenda          目次 (= 左に全項目、右にバケット。今いる章を強調する)

どの型にも無い組み方は `compose` (= `bodies/compose.py`) で書く。本体を段とマスの入れ子に割り、マスに
部品を 1 つ置く。部品には上の型も入る ― 型は組み方の短縮形で、組み方そのものではない。

⚠ **絵を持たなくてよいのは後ろの 3 つだけ** (= グラフは数字を形で見せるので、絵と同じに数える)。
本文の頁がここを外せるようになると、「表と文章だけ」の頁が戻ってくる (= 実際にそれで作った頁は
全部差し戻された)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..base.geometry import Rect
from ..base.tokens import DEFAULT, Theme
from ..parts.page import Page
from .core.frame import place_cards, place_legend, place_trailing, reserve_legend, reserve_trailing
from .core.read import MARKS, Spec
from .core.registry import check_keys, EXTRA_KEYS, FRAME_KEYS, PageTypeError, TYPES
from . import bodies  # noqa: F401 (= 本体の file を読むと、その型が登録される)
from .bodies import chart


def names() -> list[str]:
    """Every type a page may ask for."""
    return sorted(TYPES)


def skeleton() -> list[str]:
    """The types allowed to carry no figure (= the deck's own scaffolding)."""
    return sorted(name for name, spec in TYPES.items() if not spec[3])


def build(data: dict, asset: Callable[[str], Path], aspect: Callable[[Path], float],
          theme: Theme = DEFAULT) -> Page:
    """Turn one declaration into a page, refusing anything no type can hold."""
    name = str(data.get("type", "")).strip()
    if name not in TYPES:
        raise PageTypeError(
            f"unknown page type {name!r} — the deck may use only: {', '.join(names())}. "
            "A page that fits none of them means a type is missing; add one rather than "
            "placing shapes by hand."
        )
    filler, needs, takes, wants_figure = TYPES[name]
    check_keys(name, data, needs, takes)

    title = data.get("title")
    if not title:
        raise PageTypeError(f"{name}: `title` is missing — every page says what it is")

    sticker = data.get("sticker", "")
    if not isinstance(sticker, str):
        raise PageTypeError(
            f"{name}: `sticker` is {sticker!r} — a page carries one sticker, written as its words "
            '(= sticker = "Draft")')

    page = Page(
        str(title), theme,
        kicker=str(data.get("kicker", "")),
        condition=str(data.get("condition", "")),
        conclusion=str(data.get("conclusion", "")),
        footer=str(data.get("footer", "")),
        sticker=sticker.strip(),
        needs_figure=wants_figure,
    )
    spec = Spec(data, asset, aspect, theme)
    whole = page.body
    area = place_cards(page, spec, whole)
    area, trailing = reserve_trailing(page, spec, area)
    area, legend = reserve_legend(page, spec, area)
    filler(page, spec, area)
    place_legend(page, legend, Rect(area.left, whole.top, area.width, area.bottom - whole.top))
    place_trailing(page, spec, trailing)
    return page


def describe() -> str:
    """Every type and the keys each reads, from the registry itself (= never out of date)."""
    lines = ["page types (kind = \"declare\"):"]
    for name in names():
        _filler, needs, takes, figure = TYPES[name]
        needed = ", ".join(sorted(needs)) or "—"
        own = ", ".join(sorted(takes)) or "—"
        lines.append(f"  {name:<12} needs: {needed:<10} also reads: {own:<10}"
                     f"{'' if figure else '  (may carry no picture)'}")
    lines.append(f"  on any type: {', '.join(sorted(EXTRA_KEYS))}")
    lines.append(f"  a chart: kind ({' | '.join(chart.KINDS)}), categories, series = [{{ name, values, tone }}] "
                 'or data = "x.csv", highlight, unit, labels, totals (= of a waterfall), '
                 "callouts = [{ at, series, text }]")
    lines.append("  a table's cell: its words, or one mark — { harvey = 0 to 4 } (= quarters filled) "
                 f"or {{ mark = {' | '.join(MARKS)} }}")
    lines.append(f"  the frame:   {', '.join(sorted(FRAME_KEYS - {'type', 'kind'}))}")
    return "\n".join(lines)
