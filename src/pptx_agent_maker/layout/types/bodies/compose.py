"""The body written as rows of cells, nested as deep as it needs: `compose`.

**型は組み方の短縮形で、組み方そのものではない。**型だけで頁を組んでいた間は、型が想定して
いない組み方 (= 上に目標を 1 枚、下に柱を 2 枚) を書くたびに道具を直すことになり、直すまでは
指定の方を曲げて組んでいた。ここでは本体を**段 (= 上から下) とマス (= 左から右)** の入れ子で
書き、マスには部品を 1 つ置く。部品は今の型そのものも含む (= 線表を 1 マスに丸ごと入れる)。

守っているものは型の頁と同じ 3 つ:

* **座標を書く口は無い** ― 段とマスは枠を割るだけなので、頁からはみ出すことも、物どうしが
  重なることも、割り方の上で起きない
* **大きさと色は `tokens.py` の 1 枚から** ― 段とマスの間も、決まった間隔しか取れない
* **知らないキーは拒む** ― どの段のどのマスかを付けて言う

高さの決まり:

* カード・表・文章・要点だけの段は、**中身の言葉ぶんの高さ**になる (= 頁の高さを配らない)。
  同じ段のカードは、その段で一番高いカードに揃う
* 絵や型の入った段、`weight` を書いた段は、**残りの高さを `weight` の比で分け合う**
* そういう段の中に置いたカードや文章は、自分の高さのまま上に寄る
* **頁の高さを使う資料** (= `[theme] box_height = "page"`) では、カードを持つ段は、残りを取る段が無ければ、
  **残りの高さを等しく受ける** (= 字の分の高さに足す。字の多い段は字の少ない段より高いまま)。絵や型の段と
  `weight` を書いた段が残りを取るなら、カードの段は字の分のまま。カードは、置かれたマスの高さを使い切る。
  文章・表・要点は、自分の高さのまま上に寄る
* 自分の高さを持つ部品 (= 文章・表・要点・声・木・凡例と、図のマスの絵) がマスより低い時は、`valign`
  (= `"top"` `"middle"` `"bottom"`。書かなければ上端) で縦の位置を決める。表のような頁で、行の名前の文字を
  同じ段のカードの字と同じ高さに並べる時に使う。カードと入れ物はマスの高さを使い切るので書けない
* 図のマスの `inset` (= cm) は、絵の左右に取る内側の余白 (= 書かなければ 0 で、絵はマスの横幅いっぱい)。
  隣のマスとの間は変えずに、絵だけを細くする
* 同じ段のマスとマスの間は使い方の `gap_x`、段と段の間は `gap_y` (= 書かなければどちらも `gap_m`)。
  横の間だけ広げ、縦は詰める頁に使う。入れ物の中の段とマスも同じ 2 つを使う
* **空の文章 (`text = ""`) のマスは高さを取らない** (= 段の高さは同じ段のほかのマスで決まる。段の全部が空なら 0)。
  何も描かず、矢印が横切れる空きになる
* **入れ物 (`panel`)** は、中の段を同じ決まりで割る (= 中は自分の段とマスの入れ子)。入れ物の高さは、
  見出しの分と中の段の高さの合計。中に絵や型の段が在れば、入れ物は残りを取る。頁の高さを使う資料では、
  入れ物もカードと同じに、置かれたマスの高さを使い切り、中のカードはその中の高さを使う
* **入れ物と同じ段のカード**は、字を入れ物の見出しと同じ上端から置く (= `outlined` の資料でも縦の中央に置かない。
  見出しどうしが同じ高さに並ぶ)
* 残りを分け合う段の中で高さが足りずに止まった時は、外の段が取っている高さも言う (= 動かせるのはそちら)

格子 (= `grid`) の頁は、本体を段でなく**格子**で組む (= 部門をまたぐ流れ図のように、段のマスでは書けない並び):

* `grid = { columns = [1, 3, 3], rows = [1, 1] }` が列と行の幅と高さの比 (= `weight` と同じ読み方。本体を比で
  分け合い、列の間は `gap_x`、行の間は `gap_y`)
* マスは `[[cells]]`。`at = [行, 列]` (= 1 から) と `span = [行の数, 列の数]` (= 書かなければ `[1, 1]`) が格子の
  どこを覆うか。中に置ける物は段のマスと同じ。マスどうしが重なれば、どのマスとどのマスかを言って止める。
  マスの中身 (= 箱・文字・表・凡例のどれも) は、覆う範囲の四方から同じ幅 (= `gap_m` の半分) だけ内側に置く。
  **箱 (= カードと入れ物) はそこを使い切り、文章・表・要点は自分の高さのまま上に寄る** (= 行をまたぐ箱は、
  またぐどの行の箱とも向き合うので、矢印が引ける。隣り合う箱の間は、その幅の 2 つ分と列や行の間)
* 背景は `[[backdrops]]` (= `at`・`span`・`tone`)。覆う範囲いっぱいの地 (= 内側に寄せない) を、マスより下の層に敷く。
  背景どうしは重ねられない
* `rows` と `grid` は同じ頁に書けない。`cells` と `backdrops` は `grid` と対で書く
* マスの中身が入らずに止まる時は、止まる文の終わりに**入る `columns` の比を 1 組**添える (= `columns = [1.2, 1, 0.8] fits`)。
  書いた比に近く、頁の写しで組み直して入ることを確かめた物だけを言う。見つからない時は、そう言う (= 行・字・中身の側を直す)

マスの `legend = true` は、その頁で使った地の名前の凡例 (= 頁の下の凡例と同じ中身) を、そのマスの中に縦に
並べる。1 つの頁に 1 つまで。そのマスを持つ頁は、頁の下の凡例を出さない。

頁の `dotted_legend = "構想の流れ"` は、点線 (= `tentative = true` の矢印かカード) の意味。書けば、凡例の
終わりに点線の見本とその言葉を 1 項足す (= 見本の線は、矢印の点線と同じ色と太さ。頁の下でもマスの中でも同じ)。
点線の無い頁と、凡例の出ない頁に書いたら止める。書かなければ今までのまま。

⚠ **この型は図を要らない頁として扱う。**カードだけで組む頁 (= 目標と柱) を拒むと、また指定を
曲げて組むことになる。
"""

from __future__ import annotations

import copy
from numbers import Real

from ...geometry import Rect, cm
from ...parts.look import Style
from ...parts.page import CARD_ALIGNS, Card, Page, PageFullError, Panel, Voice
from ..core.frame import Legend, legend_cells, legend_of
from ..core.registry import TYPES, PageTypeError, register
from ..core.read import Spec, read_card, read_panel, read_table, read_tone, read_weight, only_keys
from ..core.stack import card_height, spread
from . import arrange
from .chart import place_chart

#: マスに 1 つ置ける部品のうち、ここで直に組む物
PARTS = ("card", "panel", "figure", "table", "text", "points", "chart", "voices", "ring", "tree", "overlap", "legend")
#: 文章の役 (= `role`)。書かなければ本文の色と大きさ。`display` = 頁の主役の数字を特大で、`label` = 列や行の
#: 見出しを太字で、`note` = 添える小さい字を灰で、`mono` = コード・コマンド・数式の行を等幅で、折らずに薄い地の枠に
ROLES = ("display", "label", "note", "mono")
#: 文章が読むキーのうち、字の見え方 (= 色の役と寄せ。`mono` は枠の中に等幅で置くので読まない)
TEXT_LOOKS = ("tone", "align")
#: 部品がマスより低い時に、マスの中で縦に置く位置 (= `valign`。書かなければ上端)
VALIGNS = ("top", "middle", "bottom")
#: 自分の高さのままマスに置かれ、`valign` で縦の位置を選べる部品 (= カードと入れ物はマスの高さを使い切り、
#: 入れ子の段・グラフ・型は渡された高さを使うので、動く先が無い)
VALIGN_PARTS = ("text", "table", "points", "voices", "tree", "legend", "figure")
#: 声 1 つが読むキー
VOICE_KEYS = ("text", "who", "tone")
#: マスに丸ごと入れられる型 (= その型の書き方のまま)。`cards` はマスごとの `card` で、
#: 入れ子は `rows` で書くので、この 2 つは入れない
BODIES = ("figures", "figure_grid", "flow", "roadmap", "timeline", "board", "agenda")
#: マスが書けるキー (= 部品のほかに、絵・文章・入れ子の段の見え方)。段のマスは `weight` を書き足せる
CELL_KEYS = frozenset({"rows", "caption", "role", "marks", "guides", "guide_tone", "valign", "inset", "id",
                       *TEXT_LOOKS, *PARTS, *BODIES})
#: 格子の頁の `grid` が読むキー (= 列と行の幅と高さの比)
GRID_KEYS = ("columns", "rows")
#: 格子のマスが書けるキー (= 段のマスと同じ物に、格子のどこを覆うか)
GRID_CELL_KEYS = frozenset({"at", "span", *CELL_KEYS})
#: 格子のマスの中身を、覆う範囲の四方から内側へ寄せる幅 (= 使い方の `gap_m` に対する比。隣り合う箱の間は、この幅の
#: 2 つ分と列や行の間になる。背景は覆う範囲いっぱいのまま)
GRID_INSET = 1 / 2
#: 入らずに止まった格子の、入る列の比を探す時に、1 つのマスが入る最小の幅を挟み込む回数 (= 本体の幅の 1 / 2 ** 8 まで
#: 狭める。比は小数 1 桁で言うので、これより細かくは要らない)
GRID_SEARCH_STEPS = 8
#: 探す時に、マス 1 つを頁の写しに置いてみる回数の上限 (= マス 1 つにつき `GRID_SEARCH_STEPS` と、今の幅・本体の幅での
#: 2 回。これを超える数のマスを持つ頁では探さず、止まる文をそのまま出す)
GRID_PROBE_LIMIT = 800
#: 見つけた比で頁を組み直して確かめる時に、マスごとの最小の幅へ足す余裕 (= 本体の幅に対する比)。比を小数 1 桁に丸めると
#: ぎりぎりのマスが入らなくなるので、入らなければ次の余裕で組み直す。この並びの長さが組み直しの回数の上限
GRID_SEARCH_MARGINS = (0.0, 0.005, 0.01, 0.02)
#: 今の幅で入るマスを、探す時にどこまで狭めてよいか (= 書いた幅に対する比)。入るというだけで狭めると、隣のマスに
#: 幅を渡して 0.2 のような列になる。これより狭くしないと入らない頁は「入る比が無い」と言う
GRID_KEEP_SHARE = 0.5
#: 幅が狭まって入らなくなるのは、字を折る・並べる部品だけ (= 絵・グラフ・入れ子の型などは渡された矩形を使う。
#: 探す時はその幅を縮めずに、今の幅を要る幅とする)
GRID_NARROWING_PARTS = ("card", "panel", "text", "points", "voices", "tree", "legend", "rows")
#: 背景が読むキー (= 覆う範囲と、地の色の役)
BACKDROP_KEYS = ("at", "span", "tone")
#: 背景が地の色を言わない時の役 (= 薄い地。箱が載る背景なので、意味を持たない地)
BACKDROP_TONE = "band"


@register("compose", needs=[], takes=["rows", "grid", "cells", "backdrops", "links", "dotted_legend", "detour"],
          figure=False)
def _compose(page: Page, spec: Spec, area: Rect) -> None:
    """Rows top to bottom (or cells on a grid), cells left to right, one part in each cell (or more rows); then the links."""
    gridded = _way(spec)
    if legend_cells(spec) > 1:
        raise PageTypeError("compose: two cells hold the legend — `legend = true` is on one cell of a page")
    seen: list[tuple[str | None, Rect, bool]] = []
    if gridded:
        _grid(page, spec, area, seen)
    else:
        _stack(page, spec, spec.get("rows"), area, "compose", seen)
    named: dict[str, Rect] = {}
    for name, rect, _blank in seen:
        if name is None:
            continue
        if name in named:
            raise PageTypeError(f"compose: two cells have the id {name!r} — an id names one cell")
        named[name] = rect
    if spec.get("links") is not None:
        arrange.links(page, spec, spec.get("links"), named, [rect for _name, rect, _blank in seen],
                      [rect for _name, rect, blank in seen if blank], "compose")


def _way(spec: Spec) -> bool:
    """Whether the body is laid out on a grid (= otherwise in rows); a page writes one way, whole."""
    rows, grid = "rows" in spec.data, "grid" in spec.data
    if rows and grid:
        raise PageTypeError("compose: `rows` and `grid` are two ways to lay out the body — a page writes one: "
                            "rows of cells, or cells on a grid")
    for key in ("cells", "backdrops"):
        if key in spec.data and not grid:
            raise PageTypeError(f"compose: `{key}` are placed on a grid — write `grid = {{ columns = [1, 1], "
                                "rows = [1, 1] }`, or write the body as rows")
    if grid and "cells" not in spec.data:
        raise PageTypeError("compose: `grid` is filled by `cells` — write [[cells]], each with its `at` (= [row, column])")
    if not rows and not grid:
        raise PageTypeError("compose: missing rows — this type is not that page without it "
                            "(= or a `grid` with its `cells`)")
    return grid


def _stack(page: Page, spec: Spec, rows, area: Rect, where: str, seen: list) -> None:
    """Lay rows down inside `area`: natural rows at their own height, the rest sharing what is left."""
    gap = page.theme.spacing.gap_y
    laid = _measure(page, spec, rows, area.width, where)
    fixed = sum(height for _row, _cells, height, _weight, _g in laid if height is not None)
    shares = sum(weight for _row, _cells, height, weight, _g in laid if height is None)
    left_over = area.height - fixed - gap * (len(laid) - 1)
    if left_over < 0 or (shares and left_over <= 0):
        raise PageFullError(
            f"{where}: the rows need {fixed + gap * (len(laid) - 1)} EMU of height before any "
            f"picture or diagram gets room, and there are {area.height} — fewer or shorter "
            "parts, or two pages; nothing will shrink")
    # 残りを取る段 (= 絵や型) が無ければ、カードを持つ段が残りを等しく受ける (= `weight` を書いた段は取る側)
    growing = sum(1 for _row, _cells, height, _weight, grows in laid if grows and height is not None)
    more = iter(spread(left_over, growing) if growing else [])
    top = area.top
    for number, (row, cells, height, weight, grows) in enumerate(laid, start=1):
        if height is None:
            tall = int(left_over * weight / shares)
        else:
            tall = height + (next(more) if grows and not shares else 0)
        # 入れ物と並ぶカードは、字を入れ物の見出しと同じ上端から置く (= 見出しどうしが同じ高さに並ぶ)
        by_panel = any("panel" in cell for cell, _column, _natural in cells)
        for index, (cell, column, natural) in enumerate(cells, start=1):
            rect = Rect(area.left + column.left, top, column.width, tall)
            at = len(seen)
            seen.append((str(cell["id"]) if "id" in cell else None, rect, _blank(cell)))
            try:
                drawn = _place(page, spec, cell, rect, natural, height is not None, f"{where}: row {number}, cell {index}",
                               seen, by_panel=by_panel)
            except PageFullError as reason:
                if height is not None or not fixed:
                    raise
                # 中で足りなくなった時、書く人が動かせるのは、この段の外で高さを取っている段の方
                raise PageFullError(
                    f"{reason} (= {where}: row {number} shares the {left_over} EMU the other rows leave of "
                    f"{area.height}, and they take {fixed} — shorter rows beside it give it more)") from reason
            if drawn is not None:
                # 矢印は描かれた矩形どうしで引く (= 入れ物が字の分の高さで止まる時は、マスより低い)
                seen[at] = (seen[at][0], drawn, seen[at][2])
        top += tall + gap


def _grid(page: Page, spec: Spec, area: Rect, seen: list) -> None:
    """Cells on a grid of columns and rows, backdrops under them.

    列と行は本体を比で分け合い (= 間は `gap_x` と `gap_y`)、背景は覆う範囲いっぱいに置く。マスの中身 (= 箱・文字・表・
    凡例のどれも) は、覆う範囲の四方から同じ幅 (= `gap_m` の `GRID_INSET`) だけ内側に置く。背景は箱より先に置く
    (= 下の層)。

    マスの中身が入らずに止まる時は、止まる文の終わりに、入る `columns` の比を 1 組添える (= `_columns_that_fit`)。
    """
    where = "compose"
    s = page.theme.spacing
    inset = round(s.gap_m * GRID_INSET)
    widths, heights = _read_grid(spec.get("grid"), where)
    try:
        across = area.columns(widths, gap=s.gap_x)
        down = area.rows(heights, gap=s.gap_y)
    except ValueError as reason:
        raise PageFullError(f"{where}: the grid is {len(widths)} columns by {len(heights)} rows, and the gaps between "
                            f"them are wider than the {area.width} x {area.height} EMU of the body — fewer columns "
                            "or rows; nothing will shrink") from reason
    backdrops = _listed(spec.get("backdrops"), "backdrops", where)
    cells = _listed(spec.get("cells"), "cells", where)
    if not cells:
        raise PageTypeError(f"{where}: `cells` is empty — write at least one [[cells]]")
    try:
        _lay(page, spec, (across, down), backdrops, cells, inset, seen)
    except PageFullError as reason:
        raise PageFullError(f"{reason}{_columns_that_fit(page, spec, area, widths, down, backdrops, cells, inset)}") from reason


def _lay(page: Page, spec: Spec, squares: tuple[list[Rect], list[Rect]], backdrops: list, cells: list, inset: int,
         seen: list) -> None:
    """The backdrops, then the cells, on the squares of a grid (= the columns and the rows, as rects)."""
    where = "compose"
    across, down = squares
    covered: dict[tuple[int, int], str] = {}
    rects = []
    for number, backdrop in enumerate(backdrops, start=1):
        what = f"{where}: backdrop {number}"
        only_keys(backdrop, set(BACKDROP_KEYS), what)
        first, last = _span_of(backdrop, len(down), len(across), what)
        _cover(covered, first, last, what)
        rects.append((_frame(across, down, first, last), read_tone(spec, backdrop, what, BACKDROP_TONE)))
    for rect, tone in rects:
        page.backdrop(rect, tone)
    covered = {}
    for number, cell in enumerate(cells, start=1):
        what = f"{where}: cell {number}"
        only_keys(cell, set(GRID_CELL_KEYS), what)
        first, last = _span_of(cell, len(down), len(across), what)
        _cover(covered, first, last, what)
        try:
            rect = _frame(across, down, first, last).inset(inset)
        except ValueError as reason:
            raise PageFullError(f"{what}: the squares it covers are too small to keep {inset} EMU round what stands "
                                "in them — fewer rows or columns, or a larger share for them; nothing will "
                                "shrink") from reason
        natural = _natural(page, spec, cell, rect.width, what)
        at = len(seen)
        seen.append((str(cell["id"]) if "id" in cell else None, rect, _blank(cell)))
        # 格子のカードは字を箱の上端から置く (= 行をまたぐカードと 1 行のカードで箱の高さが違い、縦の中央に
        # 置くと、同じ行から始まるカードの見出しの上端がずれる)
        drawn = _place(page, spec, cell, rect, natural, True, what, seen, by_panel=True)
        if drawn is not None:
            seen[at] = (seen[at][0], drawn, seen[at][2])


def _columns_that_fit(page: Page, spec: Spec, area: Rect, written: list[float], down: list[Rect], backdrops: list,
                      cells: list, inset: int) -> str:
    """The end of the words a grid stops with: the columns that make it fit, or that no columns do (= '' for neither).

    入らないマスが 1 つでもあれば、どのマスもそれぞれ入る最小の幅を測り、書いた比に近いまま全部の幅を満たす列の比を
    作る。作った比は頁の写しで組み直して入ることを確かめてから言う (= 確かめていない比は出さない)。行の比は変えない。
    マスの数が `GRID_PROBE_LIMIT` で測れない頁と、マスそのものの書き間違いがある頁では、何も足さない。
    """
    if len(cells) * (GRID_SEARCH_STEPS + 2) > GRID_PROBE_LIMIT:
        return ""
    try:
        shares = _fitting_shares(page, spec, area, written, down, backdrops, cells, inset)
    except PageTypeError:
        return ""
    if shares is None:
        return (" — no ratio of the columns makes everything fit (= with no cell less than half as wide as written); "
                "the rows, the words, or what stands in the cells have to change")
    return f" — columns = [{', '.join(f'{share:g}' for share in shares)}] fits"


def _fitting_shares(page: Page, spec: Spec, area: Rect, written: list[float], down: list[Rect], backdrops: list,
                    cells: list, inset: int) -> list[float] | None:
    """Shares of the columns, to one decimal and in the sum of the written ones, that the grid is built with; None when none is found."""
    gap = page.theme.spacing.gap_x
    across = area.columns(written, gap=gap)
    total = sum(column.width for column in across)
    base = [column.width for column in across]
    needs = []
    for number, cell in enumerate(cells, start=1):
        what = f"compose: cell {number}"
        first, last = _span_of(cell, len(down), len(across), what)
        try:
            height = _frame(across, down, first, last).inset(inset).height
        except ValueError:
            return None                           # 行が低すぎて余白が取れない: 列の比では直らない
        gaps = gap * (last[1] - first[1])
        spanned = sum(base[first[1]:last[1] + 1]) + gaps
        least = _least_width(page, spec, cell, spanned - 2 * inset, height, area.width - 2 * inset, what)
        if least is None:
            return None
        needs.append((first[1], last[1], least + 2 * inset - gaps))
    for margin in GRID_SEARCH_MARGINS:
        widths = _widths_near(base, [(first, last, need + round(margin * total)) for first, last, need in needs])
        if widths is None:
            return None
        shares = [max(round(width / total * sum(written), 1), 0.1) for width in widths]
        try:
            squares = (area.columns(shares, gap=gap), down)
            _lay(_scratch(page), spec, squares, backdrops, cells, inset, [])
        except PageFullError:
            continue
        return shares
    return None


def _least_width(page: Page, spec: Spec, cell: dict, width: int, height: int, wide: int, what: str) -> int | None:
    """The narrowest a cell can be and still fit, kept to a row `height` tall; None when even the whole body `wide` is too narrow.

    幅が狭くなって入らなくなるのは字を折る部品だけなので、それ以外は今の幅 `width` を、縮めずに要る幅とする。
    入る幅と入らない幅で挟み込む (= 幅が広いほど入りやすいとして)。今の幅で入るマスは `GRID_KEEP_SHARE` までしか狭めない。
    """
    if _part(cell, what) not in GRID_NARROWING_PARTS:
        return width

    def fits(at: int) -> bool:
        return _fits(page, spec, cell, Rect(0, 0, at, height), what)

    if fits(width):
        low, high = round(width * GRID_KEEP_SHARE), width
        if fits(low):
            return low
    elif fits(wide):
        low, high = width, wide
    else:
        return None
    for _ in range(GRID_SEARCH_STEPS):
        middle = (low + high) // 2
        low, high = (low, middle) if fits(middle) else (middle, high)
    return high


def _fits(page: Page, spec: Spec, cell: dict, rect: Rect, what: str) -> bool:
    """Whether a cell's part is placed in that rect without stopping (= tried on a scratch copy of the page)."""
    trial = _scratch(page)
    try:
        _place(trial, spec, cell, rect, _natural(trial, spec, cell, rect.width, what), True, what, [], by_panel=True)
    except PageFullError:
        return False
    return True


def _scratch(page: Page) -> Page:
    """A copy of the page to try a layout on (= what is placed on it never reaches the page)."""
    copied = copy.copy(page)
    copied.elements = []
    return copied


def _widths_near(written: list[int], needs: list[tuple[int, int, int]]) -> list[float] | None:
    """Widths of the columns that hold every need and are the nearest to the written ones; None when the body is too narrow.

    `needs` = (first column, last column, the width that span has to add up to). 足りない列は要る幅まで上げ、その
    ぶんは余裕のある列から、余裕に比例して取る (= 余裕の無い列は動かない)。複数の列をまたぐマスは、足りない
    ぶんをまたぐ列に今の幅の比で足す。一度満たした要りようは下げた幅で崩れない (= 下限として残る)ので、
    マスの数を超えて回らない。
    """
    floors = [0.0] * len(written)
    for _ in range(len(needs) + 1):
        widths = _shifted(written, floors)
        if widths is None:
            return None
        short = [(first, last, need - sum(widths[first:last + 1])) for first, last, need in needs
                 if sum(widths[first:last + 1]) < need]
        if not short:
            return widths
        for first, last, lack in short:
            held = sum(widths[first:last + 1])
            for column in range(first, last + 1):
                floors[column] = max(floors[column], widths[column] + lack * widths[column] / held)
    return None


def _shifted(written: list[int], floors: list[float]) -> list[float] | None:
    """The written widths with every column below its floor raised to it, the same width taken off the columns above theirs; None when they cannot."""
    raised = sum(max(floor - width, 0) for width, floor in zip(written, floors))
    slack = [max(width - floor, 0) for width, floor in zip(written, floors)]
    if raised > sum(slack) + 1e-6:
        return None
    if not raised:
        return [float(width) for width in written]
    return [floor if width < floor else width - raised * spare / sum(slack)
            for width, floor, spare in zip(written, floors, slack)]


def _read_grid(grid, where: str) -> tuple[list[float], list[float]]:
    """The shares the columns and the rows of a grid take: `{ columns = [1, 3], rows = [1, 1] }`."""
    what = f"{where}: grid"
    only_keys(grid, set(GRID_KEYS), what)
    shares = []
    for key in GRID_KEYS:
        written = grid.get(key)
        if not isinstance(written, list) or not written:
            raise PageTypeError(f"{what}: `{key}` is a list of shares, one for each of the {key} of the grid, "
                                f"as in {key} = [1, 1]")
        shares.append([read_weight({"weight": share}, f"{what}, {key}") for share in written])
    return shares[0], shares[1]


def _listed(written, key: str, where: str) -> list:
    """A list of tables a page writes (= `cells`, `backdrops`); nothing when it does not write it."""
    if written is None:
        return []
    if not isinstance(written, list):
        raise PageTypeError(f"{where}: `{key}` is a list of tables, written [[{key}]]")
    return written


def _span_of(item: dict, rows: int, columns: int, what: str) -> tuple[tuple[int, int], tuple[int, int]]:
    """The first and the last (row, column) a cell or a backdrop covers, from 0: `at = [row, column]`, `span = [rows, columns]`."""
    at = _pair(item, "at", None, what, "the row and the column of its top left corner, from 1, as in at = [1, 2]")
    span = _pair(item, "span", (1, 1), what, "how many rows and how many columns it covers, as in span = [2, 1] "
                 "(= 1 and 1 when left out)")
    last = (at[0] + span[0] - 2, at[1] + span[1] - 2)
    for number, (name, bound) in enumerate((("row", rows), ("column", columns))):
        if last[number] >= bound:
            raise PageTypeError(f"{what}: covers {name} {last[number] + 1}, and the grid has {bound} {name}s — "
                                f"`at` and `span` stay inside it")
    return (at[0] - 1, at[1] - 1), last


def _pair(item: dict, key: str, unsaid: tuple[int, int] | None, what: str, means: str) -> tuple[int, int]:
    """Two whole numbers from 1 (= `at`, `span`); `unsaid` when it is left out (= required when that is None)."""
    if key not in item:
        if unsaid is None:
            raise PageTypeError(f"{what} has no `{key}` — it is {means}")
        return unsaid
    written = item[key]
    if (not isinstance(written, list) or len(written) != 2
            or any(isinstance(number, bool) or not isinstance(number, int) or number < 1 for number in written)):
        raise PageTypeError(f"{what}: `{key}` is {means}, not {written!r}")
    return written[0], written[1]


def _cover(covered: dict, first: tuple[int, int], last: tuple[int, int], what: str) -> None:
    """Mark the squares of the grid a cell or a backdrop covers; refuse one that a cell of its kind covers already."""
    for row in range(first[0], last[0] + 1):
        for column in range(first[1], last[1] + 1):
            if (row, column) in covered:
                raise PageTypeError(f"{what} and {covered[(row, column)]} both cover row {row + 1}, column {column + 1} "
                                    "— a square of a grid is covered by one cell, and by one backdrop")
            covered[(row, column)] = what.removeprefix("compose: ")


def _frame(across: list[Rect], down: list[Rect], first: tuple[int, int], last: tuple[int, int]) -> Rect:
    """The rect from the top left of the first square to the bottom right of the last (= the gaps between them included)."""
    left, top = across[first[1]].left, down[first[0]].top
    return Rect(left, top, across[last[1]].right - left, down[last[0]].bottom - top)


def _blank(cell: dict) -> bool:
    """Whether a cell holds nothing (= `text = ""`): space a link may cross, and words may stand over.

    コードの枠 (= `role = "mono"`) は、中が空でも枠が見える物なので、空きに数えない。
    """
    return "text" in cell and cell.get("role") != "mono" and not str(cell["text"]).strip()


def _grows(page: Page, cell: dict) -> bool:
    """Whether a cell holds boxes that take the height their row has (= a card, a panel, or rows with one inside).

    頁の高さを使う資料 (= `box_height = "page"`) でだけ、カードと入れ物は字の分の高さで止まらない。
    """
    if page.theme.box_height != "page":
        return False
    return "card" in cell or "panel" in cell or any(_grows(page, inner) for row in cell.get("rows", []) for inner in row["cells"])


def _measure(page: Page, spec: Spec, rows, width: int, where: str):
    """Each row with its cells, the row's own height (None = it shares the rest), its share, and whether it grows."""
    if not isinstance(rows, list) or not rows:
        raise PageTypeError(f"{where}: `rows` is empty — write at least one [[…rows]] with its cells")
    gap = page.theme.spacing.gap_x
    laid = []
    for number, row in enumerate(rows, start=1):
        what = f"{where}: row {number}"
        only_keys(row, {"cells", "weight"}, what)
        cells = row.get("cells")
        if not isinstance(cells, list) or not cells:
            raise PageTypeError(f"{what} has no cells — write [[…cells]] under it, one per part")
        for index, cell in enumerate(cells, start=1):
            only_keys(cell, {"weight", *CELL_KEYS}, f"{what}, cell {index}")
        weights = [read_weight(cell, f"{what}, cell {index}") for index, cell in enumerate(cells, start=1)]
        columns = Rect(0, 0, width, 1).columns(weights, gap=gap)
        measured = [(cell, column, _natural(page, spec, cell, column.width, f"{what}, cell {index}"))
                    for index, (cell, column) in enumerate(zip(cells, columns), start=1)]
        shares = "weight" in row
        naturals = [natural for _cell, _column, natural in measured]
        height = None if shares or None in naturals else max(naturals)
        laid.append((row, measured, height, read_weight(row, what), any(_grows(page, cell) for cell in cells)))
    return laid


def _part(cell: dict, what: str) -> str:
    """The one thing a cell holds."""
    named = [key for key in ("rows", *PARTS, *BODIES) if key in cell]
    if not named:
        raise PageTypeError(
            f"{what} holds nothing — give it one of: {', '.join(('rows',) + PARTS + BODIES)}")
    if len(named) > 1:
        raise PageTypeError(
            f"{what} holds {', '.join(named)} — one part per cell; put the others in cells beside it")
    if "legend" in cell and cell["legend"] is not True:
        raise PageTypeError(f"{what}: `legend` is true (= the cell holds the legend of the grounds this page uses), "
                            f"not {cell['legend']!r}")
    if "caption" in cell and named[0] != "figure":
        raise PageTypeError(f"{what}: `caption` belongs to a figure, and this cell holds {named[0]}")
    if "marks" in cell and named[0] != "figure":
        raise PageTypeError(f"{what}: `marks` belong to a figure, and this cell holds {named[0]}")
    for key in ("guides", "guide_tone", "inset"):
        if key in cell and named[0] != "figure":
            raise PageTypeError(f"{what}: `{key}` belongs to a figure, and this cell holds {named[0]}")
    if "valign" in cell:
        if named[0] not in VALIGN_PARTS:
            raise PageTypeError(f"{what}: `valign` places a part that keeps its own height ({', '.join(VALIGN_PARTS)}) "
                                f"in its cell, and a {named[0]} takes the height of its cell — there is nowhere to move it")
        if cell["valign"] not in VALIGNS:
            raise PageTypeError(
                f"{what}: `valign` is {' or '.join(repr(name) for name in VALIGNS)}, not {cell['valign']!r}")
    if "inset" in cell:
        inset = cell["inset"]
        if isinstance(inset, bool) or not isinstance(inset, Real) or inset < 0:
            raise PageTypeError(f"{what}: `inset` is the room left and right of the picture in cm, "
                                f"0 or more, not {inset!r}")
    for key in ("valign", "inset"):
        if key in cell and "marks" in cell:
            raise PageTypeError(f"{what}: a figure with `marks` stands where its names put it — "
                                f"`{key}` is for a figure without them")
    if "guides" in cell and "marks" in cell:
        raise PageTypeError(f"{what}: a figure carries `marks` or `guides`, not both — the names beside the picture "
                            "and the rules across it are two ways to read the same height")
    if "role" in cell:
        if named[0] != "text":
            raise PageTypeError(f"{what}: `role` belongs to a text, and this cell holds {named[0]}")
        if cell["role"] not in ROLES:
            raise PageTypeError(f"{what}: `role` is one of {', '.join(ROLES)}, not {cell['role']!r}")
    for key in TEXT_LOOKS:
        if key in cell and (named[0] != "text" or cell.get("role") == "mono"):
            holds = "a mono text (= code is set in its own box)" if named[0] == "text" else named[0]
            raise PageTypeError(f"{what}: `{key}` belongs to a text of words, and this cell holds {holds}")
    if "align" in cell and cell["align"] not in CARD_ALIGNS:
        raise PageTypeError(
            f"{what}: `align` is {' or '.join(repr(name) for name in CARD_ALIGNS)}, not {cell['align']!r}")
    return named[0]


def _guides(spec: Spec, cell: dict, what: str) -> tuple[tuple[float, ...], str]:
    """The heights a figure is ruled at (= shares of the picture's height, from its top) and the tone of the rules.

    線の色の役は `guide_tone` (= 書かなければ `accent`)。色の決まりは `Page.tone_ink` が読む。
    """
    if "guides" not in cell:
        if "guide_tone" in cell:
            raise PageTypeError(f"{what}: `guide_tone` is the colour of the rules `guides` draws, and this cell has none")
        return (), ""
    listed = cell["guides"]
    if not isinstance(listed, list) or not listed:
        raise PageTypeError(f"{what}: `guides` is a list of numbers between 0 and 1 (= how far down the picture "
                            "each rule falls), as in [0.25, 0.5, 0.75]")
    for value in listed:
        if isinstance(value, bool) or not isinstance(value, Real) or not 0 < value < 1:
            raise PageTypeError(f"{what}: `guides` holds {value!r} — a rule falls at a share of the picture's "
                                "height, a number above 0 and below 1")
    tone = read_tone(spec, {"tone": cell.get("guide_tone", "accent")}, f"{what}: `guide_tone`", "accent")
    return tuple(float(value) for value in listed), tone


def _natural(page: Page, spec: Spec, cell: dict, width: int, what: str) -> int | None:
    """How tall a cell is for its own words, or None when it takes whatever room it is given."""
    part = _part(cell, what)
    theme, s = page.theme, page.theme.spacing
    if part == "card":
        return card_height(page, [_the_card(spec, cell, what)], width, 1)
    if part == "panel":
        panel = _the_panel(spec, cell, what)
        inside = max(width - 2 * s.pad, 1)
        laid = _measure(page, spec, cell["panel"]["rows"], inside, f"{what}, panel")
        if any(height is None for _row, _cells, height, _weight, _g in laid):
            return None
        return (sum(height for _r, _c, height, _w, _g in laid) + s.gap_y * (len(laid) - 1)
                + page.panel_head(panel, inside) + 2 * s.pad)
    if part == "table":
        rows = _table(spec, cell, what)
        return theme.table_height(rows, theme.column_widths(rows, width))
    if part == "legend":
        legend = _legend(page, spec, what)
        if page.legend_width(legend.names, dotted=legend.dotted) > width:
            raise PageFullError(f"{what}: the legend needs {page.legend_width(legend.names, dotted=legend.dotted)} EMU of "
                                f"width and the cell has {width} — a wider cell, or shorter names; nothing will shrink")
        return page.legend_height(width, legend.names, dotted=legend.dotted, down=True)
    if part == "text" and cell.get("role") == "mono":
        try:
            return page.code_height(width, str(cell["text"]))
        except PageFullError as reason:
            raise PageFullError(f"{what}: {reason}") from reason
    if part == "text" and _blank(cell):
        return 0                                  # 空のマスは字の 1 行ぶんも取らない
    if part == "text":
        size, bold = page.text_face(cell.get("role"))
        return theme.wrapped_height(str(cell["text"]), max(width - 2 * s.text_inset, 1), size, bold=bold)
    if part == "points":
        return page.points_height(width, _points(cell, what))
    if part == "voices":
        return page.voices_height(width, _voices(spec, cell, what))
    if part == "tree":
        try:
            return arrange.tree_height(page, arrange.tree_root(spec, cell["tree"], f"{what}, tree"), width)
        except PageFullError as reason:
            raise PageFullError(f"{what}: {reason}") from reason
    if part == "rows":
        laid = _measure(page, spec, cell["rows"], width, what)
        if any(height is None for _row, _cells, height, _weight, _g in laid):
            return None
        return sum(height for _r, _c, height, _w, _g in laid) + s.gap_y * (len(laid) - 1)
    if part == "figure":
        _guides(spec, cell, what)                 # 線の書き方の誤りは、置く前の測りで止める
    return None                                   # 絵と型は、渡された高さをそのまま使う


def _place(page: Page, spec: Spec, cell: dict, rect: Rect, natural: int | None, own_row: bool,
           what: str, seen: list, *, by_panel: bool = False) -> Rect | None:
    """Put one cell's part in its rect; the rect an enclosure is drawn in when that is not the cell's (= otherwise None).

    `own_row` は、段が中身の言葉ぶんの高さの段か (= その段のカードは段の高さに揃える)。
    `by_panel` は、同じ段に入れ物が在るか (= カードの字を、入れ物の見出しと同じ上端から置く)。
    残りを分け合う段では、自分の高さを持つ部品は自分の高さのまま上に寄る (= 頁の高さを配らない)。
    頁の高さを使う資料 (= `box_height = "page"`) では、カードと入れ物はどの段でも置かれたマスを使い切る。

    ⚠ **分け合う段が、自分の高さを持つ部品より低ければ止まる。**段の高さに切り詰めて置いていた間は、
    カードの字が箱からはみ出し、文章の枠は字より短かった。入れ子の段と表は、自分で同じことを言う。
    """
    part = _part(cell, what)
    if natural is not None and natural > rect.height and part in ("card", "panel", "text", "points", "voices", "tree", "legend"):
        raise PageFullError(
            f"{what}: this {part} needs {natural} EMU of height and its row has {rect.height} — "
            "give the row a larger `weight`, or take something off the page; nothing will shrink")
    fitted = rect if natural is None else _stood(rect, min(natural, rect.height), cell.get("valign", "top"))
    try:
        if part == "card":
            page.boxes(rect if own_row or page.theme.box_height == "page" else fitted, [_the_card(spec, cell, what)],
                       top=by_panel)
        elif part == "panel":
            return _panel(page, spec, cell, rect if own_row or page.theme.box_height == "page" else fitted, what, seen)
        elif part == "table":
            page.table(fitted, _table(spec, cell, what))
        elif part == "text" and cell.get("role") == "mono":
            page.code(fitted, str(cell["text"]))
        elif part == "text" and _blank(cell):
            pass                                  # 空のマスは何も描かない (= 高さも無い)
        elif part == "text":
            tone = read_tone(spec, cell, what, "box") if "tone" in cell else None
            page.text(fitted, str(cell["text"]), role=cell.get("role"), tone=tone, align=cell.get("align", "left"))
        elif part == "legend":
            legend = _legend(page, spec, what)
            page.legend(fitted, legend.names, dotted=legend.dotted, down=True)
        elif part == "points":
            page.points(fitted, _points(cell, what))
        elif part == "voices":
            page.voices(fitted, _voices(spec, cell, what))
        elif part == "rows":
            _stack(page, spec, cell["rows"], rect, what, seen)
        elif part == "ring":
            arrange.ring(page, rect, arrange.ring_cards(spec, cell["ring"], f"{what}, ring"), what)
        elif part == "tree":
            arrange.tree(page, fitted, arrange.tree_root(spec, cell["tree"], f"{what}, tree"), what)
        elif part == "overlap":
            sets, shared = arrange.overlap_sets(spec, cell["overlap"], f"{what}, overlap")
            arrange.overlap(page, rect, sets, shared, what)
        elif part == "chart":
            place_chart(page, spec, cell["chart"], rect, f"{what}, chart")
        elif part == "figure":
            # 絵は横幅いっぱいで、`valign` を書かなければ上に寄る (= 同じ段の表や文章と上端が揃う)。縦が足りなければ縮む
            source, aspect = Spec({"figure": cell["figure"]}, spec.asset, spec.aspect, spec.theme).figure()
            caption = str(cell.get("caption", ""))
            if "marks" in cell:
                arrange.marked_figure(page, rect, source, aspect, arrange.read_marks(cell["marks"], what),
                                      caption, what)
                return
            s = page.theme.spacing
            inset = cm(cell.get("inset", 0))
            if 2 * inset >= rect.width:
                raise PageFullError(f"{what}: `inset` leaves {inset} EMU on each side of a cell {rect.width} EMU "
                                    "wide, and no room for the picture — a smaller `inset`, or a wider cell")
            frame = rect.inset(x=inset)
            wanted = round(frame.width / aspect) + (
                s.gap_s + page.theme.caption_height(caption, frame.width) if caption else 0)
            block = min(wanted, frame.height)
            placed = page.figure(_stood(frame, block, cell.get("valign", "top")), source, aspect, caption=caption)
            shares, tone = _guides(spec, cell, what)
            for share in shares:
                y = placed.top + round(share * placed.height)
                page.line((placed.left, y), (placed.right, y), tone=tone)
        else:
            if not isinstance(cell[part], dict):
                raise PageTypeError(f"{what}: `{part}` is a table of that type's own keys")
            _body(page, spec, part, cell[part], rect, what)
    except (PageTypeError, PageFullError) as reason:
        if str(reason).startswith(what):
            raise
        raise type(reason)(f"{what}: {reason}") from reason
    except ValueError as reason:
        raise PageTypeError(f"{what}: {reason}") from reason


def _stood(rect: Rect, height: int, valign: str) -> Rect:
    """Where in its cell `rect` a part `height` tall stands: at the top, in the middle or at the bottom (= `valign`)."""
    spare = rect.height - height                  # 部品がマスより低い時の余り (= マスの高さを使い切る時は 0)
    return Rect(rect.left, rect.top + {"top": 0, "middle": spare // 2, "bottom": spare}[valign], rect.width, height)


def _panel(page: Page, spec: Spec, cell: dict, rect: Rect, what: str, seen: list) -> Rect:
    """A panel in its rect, and the rows it holds divided in what is left inside it (= the rect it was drawn in).

    中の段は、段とマスの組み方をそのまま使う (= `_stack`)。中のマスの `id` も `links` に使える。

    ⚠ **濃い地の箱の中へ、字を直に置かない。**塗りのカードの資料で、差し色などの役の箱は地が濃く、字は紙の色で
    置く。中へ直に置く文章・要点・表・グラフ・声・並べ方の字は本文の色や灰なので、読めない (= 検査が後から
    言うことになる)。許すのは、自分の地を持つ物 (= カード・入れ物・コードの枠) と、名の無い絵だけ。
    """
    panel = _the_panel(spec, cell, what)
    where = f"{what}, panel"
    if not page.reads_ink(panel.style):
        bare = _bare(cell["panel"]["rows"])
        if bare:
            raise PageTypeError(
                f"{where}: a {bare} stands straight on the ground of this panel, which is deep in this look "
                f"(= tone {panel.style.tone!r}), and the ink of the body does not read on it — put it in a card, "
                "give the panel a pale tone, or set the deck's `card_look` to \"outlined\"")
    _stack(page, spec, cell["panel"]["rows"], page.panel(rect, panel), where, seen)
    return rect


#: 濃い地の箱の中へ直に置いても読める部品 (= 自分の地を持つ物と、字を持たない絵。名や印の付いた絵は下で外す)
OWN_GROUND = ("card", "panel", "figure")


def _bare(rows) -> str:
    """The first part under these rows that would stand straight on the ground of the box above it (= '' for none).

    入れ子の段は下まで見る。入れ物とカードの中は、その箱の地の上なので見ない。
    """
    for row in rows:
        for cell in row["cells"]:
            if "rows" in cell:
                found = _bare(cell["rows"])
                if found:
                    return found
                continue
            named = next((key for key in (*PARTS, *BODIES) if key in cell), "")
            if named == "text" and cell.get("role") == "mono":
                continue
            if named == "figure" and ("caption" in cell or "marks" in cell):
                return "figure with its words"
            if named and named not in OWN_GROUND:
                return named
    return ""


def _body(page: Page, spec: Spec, name: str, data: dict, rect: Rect, what: str) -> None:
    """A whole page type, laid into one cell, read the way that type reads it."""
    filler, needs, takes, _figure = TYPES[name]
    missing = sorted(needs - data.keys())
    if missing:
        raise PageTypeError(f"{name}: missing {', '.join(missing)} — this type is not that part without it")
    unknown = sorted(data.keys() - needs - takes)
    if unknown:
        raise PageTypeError(
            f"{name}: does not take {', '.join(unknown)} inside a cell (= it reads "
            f"{', '.join(sorted(needs | takes))}; cards, tables and words go in cells of their own)")
    filler(page, Spec(data, spec.asset, spec.aspect, spec.theme), rect)


def _the_card(spec: Spec, cell: dict, what: str) -> Card:
    return read_card(spec, cell["card"], f"{what}, card")


def _the_panel(spec: Spec, cell: dict, what: str) -> Panel:
    return read_panel(spec, cell["panel"], f"{what}, panel")


def _table(spec: Spec, cell: dict, what: str) -> list[list[str]]:
    return read_table(cell["table"], f"{what}: table", spec.asset)


def _voices(spec: Spec, cell: dict, what: str) -> list[Voice]:
    """What people said, each `{ text = "…", who = "…", tone = "…" }` (= `who` and `tone` may be left out)."""
    listed = cell["voices"]
    if not isinstance(listed, list) or not listed:
        raise PageTypeError(f"{what}: `voices` is a list of {{ text = …, who = … }}, at least one")
    found = []
    for number, item in enumerate(listed, start=1):
        where = f"{what}: voice {number}"
        if not isinstance(item, dict):
            raise PageTypeError(f"{where} is {item!r} — write it as {{ text = \"…\", who = \"…\" }}")
        only_keys(item, set(VOICE_KEYS), where)
        text = str(item.get("text", "")).strip()
        if not text:
            raise PageTypeError(f"{where} has no `text` — a voice is what someone said")
        found.append(Voice(text, str(item.get("who", "")).strip(),
                           Style(read_tone(spec, item, where, "box") if "tone" in item else "box")))
    return found


def _legend(page: Page, spec: Spec, what: str) -> Legend:
    """What a legend cell lists: the grounds the project named that this page uses (= what the legend under a page lists), and the words of the dotted line."""
    legend = legend_of(page, spec)
    if not legend.names:
        raise PageTypeError(f"{what}: `legend = true` lists the grounds this page uses that the project named in "
                            "[theme.grounds], and this page uses none — drop the cell")
    return legend


def _points(cell: dict, what: str) -> list[str]:
    items = cell["points"]
    if isinstance(items, str):
        items = items.split("\n")
    if not isinstance(items, list):
        raise PageTypeError(f"{what}: `points` is a list of lines")
    lines = [str(item) for item in items if str(item).strip()]
    if not lines:
        raise PageTypeError(f"{what}: `points` is empty — drop the cell rather than leaving it blank")
    return lines
