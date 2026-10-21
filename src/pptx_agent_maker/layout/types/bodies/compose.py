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
* 図のマスの絵がマスより低い時は、`valign` (= `"top"` `"middle"` `"bottom"`。書かなければ上端) で縦の位置を決める
* 図のマスの `inset` (= cm) は、絵の左右に取る内側の余白 (= 書かなければ 0 で、絵はマスの横幅いっぱい)。
  隣のマスとの間は変えずに、絵だけを細くする
* 同じ段のマスとマスの間は使い方の `gap_x`、段と段の間は `gap_y` (= 書かなければどちらも `gap_m`)。
  横の間だけ広げ、縦は詰める頁に使う。入れ物の中の段とマスも同じ 2 つを使う
* **空の文章 (`text = ""`) のマスは高さを取らない** (= 段の高さは同じ段のほかのマスで決まる。段の全部が空なら 0)。
  何も描かず、矢印が横切れる空きになる
* **入れ物 (`panel`)** は、中の段を同じ決まりで割る (= 中は自分の段とマスの入れ子)。入れ物の高さは、
  見出しの分と中の段の高さの合計。中に絵や型の段が在れば、入れ物は残りを取る。頁の高さを使う資料では、
  入れ物もカードと同じに、置かれたマスの高さを使い切り、中のカードはその中の高さを使う

⚠ **この型は図を要らない頁として扱う。**カードだけで組む頁 (= 目標と柱) を拒むと、また指定を
曲げて組むことになる。
"""

from __future__ import annotations

from numbers import Real

from ...base.geometry import Rect, cm
from ...parts.look import Style
from ...parts.page import CARD_ALIGNS, Card, Page, PageFullError, Panel, Voice
from ..core.registry import TYPES, PageTypeError, register
from ..core.read import Spec, read_card, read_panel, read_table, read_tone, read_weight, only_keys
from ..core.stack import card_height, spread
from . import arrange
from .chart import place_chart

#: マスに 1 つ置ける部品のうち、ここで直に組む物
PARTS = ("card", "panel", "figure", "table", "text", "points", "chart", "voices", "ring", "tree", "overlap")
#: 文章の役 (= `role`)。書かなければ本文の色と大きさ。`display` = 頁の主役の数字を特大で、`label` = 列や行の
#: 見出しを太字で、`note` = 添える小さい字を灰で、`mono` = コード・コマンド・数式の行を等幅で、折らずに薄い地の枠に
ROLES = ("display", "label", "note", "mono")
#: 文章が読むキーのうち、字の見え方 (= 色の役と寄せ。`mono` は枠の中に等幅で置くので読まない)
TEXT_LOOKS = ("tone", "align")
#: 絵がマスより低い時に、マスの中で縦に置く位置 (= `valign`。書かなければ上端)
VALIGNS = ("top", "middle", "bottom")
#: 声 1 つが読むキー
VOICE_KEYS = ("text", "who", "tone")
#: マスに丸ごと入れられる型 (= その型の書き方のまま)。`cards` はマスごとの `card` で、
#: 入れ子は `rows` で書くので、この 2 つは入れない
BODIES = ("figures", "figure_grid", "flow", "roadmap", "timeline", "board", "agenda")


@register("compose", needs=["rows"], takes=["links"], figure=False)
def _compose(page: Page, spec: Spec, area: Rect) -> None:
    """Rows top to bottom, cells left to right, one part in each cell (or more rows); then the links."""
    seen: list[tuple[str | None, Rect, bool]] = []
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
        for index, (cell, column, natural) in enumerate(cells, start=1):
            rect = Rect(area.left + column.left, top, column.width, tall)
            at = len(seen)
            seen.append((str(cell["id"]) if "id" in cell else None, rect, _blank(cell)))
            drawn = _place(page, spec, cell, rect, natural, height is not None, f"{where}: row {number}, cell {index}", seen)
            if drawn is not None:
                # 矢印は描かれた矩形どうしで引く (= 入れ物が字の分の高さで止まる時は、マスより低い)
                seen[at] = (seen[at][0], drawn, seen[at][2])
        top += tall + gap


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
            only_keys(cell, {"weight", "rows", "caption", "role", "marks", "guides", "guide_tone", "valign", "inset", "id",
                             *TEXT_LOOKS, *PARTS, *BODIES}, f"{what}, cell {index}")
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
    if "caption" in cell and named[0] != "figure":
        raise PageTypeError(f"{what}: `caption` belongs to a figure, and this cell holds {named[0]}")
    if "marks" in cell and named[0] != "figure":
        raise PageTypeError(f"{what}: `marks` belong to a figure, and this cell holds {named[0]}")
    for key in ("guides", "guide_tone", "valign", "inset"):
        if key in cell and named[0] != "figure":
            raise PageTypeError(f"{what}: `{key}` belongs to a figure, and this cell holds {named[0]}")
    if "valign" in cell:
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
        rows = _table(cell, what)
        return theme.table_height(rows, theme.column_widths(rows, width))
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
           what: str, seen: list) -> Rect | None:
    """Put one cell's part in its rect; the rect an enclosure is drawn in when that is not the cell's (= otherwise None).

    `own_row` は、段が中身の言葉ぶんの高さの段か (= その段のカードは段の高さに揃える)。
    残りを分け合う段では、自分の高さを持つ部品は自分の高さのまま上に寄る (= 頁の高さを配らない)。
    頁の高さを使う資料 (= `box_height = "page"`) では、カードと入れ物はどの段でも置かれたマスを使い切る。

    ⚠ **分け合う段が、自分の高さを持つ部品より低ければ止まる。**段の高さに切り詰めて置いていた間は、
    カードの字が箱からはみ出し、文章の枠は字より短かった。入れ子の段と表は、自分で同じことを言う。
    """
    part = _part(cell, what)
    if natural is not None and natural > rect.height and part in ("card", "panel", "text", "points", "voices", "tree"):
        raise PageFullError(
            f"{what}: this {part} needs {natural} EMU of height and its row has {rect.height} — "
            "give the row a larger `weight`, or take something off the page; nothing will shrink")
    fitted = rect if natural is None else Rect(rect.left, rect.top, rect.width, min(natural, rect.height))
    try:
        if part == "card":
            page.boxes(rect if own_row or page.theme.box_height == "page" else fitted, [_the_card(spec, cell, what)])
        elif part == "panel":
            return _panel(page, spec, cell, rect if own_row or page.theme.box_height == "page" else fitted, what, seen)
        elif part == "table":
            page.table(fitted, _table(cell, what))
        elif part == "text" and cell.get("role") == "mono":
            page.code(fitted, str(cell["text"]))
        elif part == "text" and _blank(cell):
            pass                                  # 空のマスは何も描かない (= 高さも無い)
        elif part == "text":
            tone = read_tone(spec, cell, what, "box") if "tone" in cell else None
            page.text(fitted, str(cell["text"]), role=cell.get("role"), tone=tone, align=cell.get("align", "left"))
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
            s, ty = page.theme.spacing, page.theme.type
            inset = cm(cell.get("inset", 0))
            if 2 * inset >= rect.width:
                raise PageFullError(f"{what}: `inset` leaves {inset} EMU on each side of a cell {rect.width} EMU "
                                    "wide, and no room for the picture — a smaller `inset`, or a wider cell")
            frame = rect.inset(x=inset)
            wanted = round(frame.width / aspect) + (
                s.gap_s + page.theme.wrapped_height(caption, max(frame.width - 2 * s.text_inset, 1),
                                                    ty.caption) if caption else 0)
            block = min(wanted, frame.height)
            spare = frame.height - block                # 絵がマスより低い時の余り (= 絵が縦に詰められた時は 0)
            top = frame.top + {"top": 0, "middle": spare // 2, "bottom": spare}[cell.get("valign", "top")]
            placed = page.figure(Rect(frame.left, top, frame.width, block), source, aspect, caption=caption)
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


def _table(cell: dict, what: str) -> list[list[str]]:
    return read_table(cell["table"], f"{what}: table")


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
