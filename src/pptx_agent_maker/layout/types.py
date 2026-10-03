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
到達点までの道のりを矢羽根の図形のまま組む。

    figure          絵 1 枚が本体
    figures         絵を横に並べる (= 条件ちがいの比較)
    figure_grid     絵を格子に並べる (= 対象 × 条件のような 2 軸)
    flow            段が左から右へ流れる (= 各段にノード、段の下に分かったこと)
    roadmap         到達点までの段が矢羽根で左から右へ (= 各段の下に、その段で渡す物)
    timeline        期間が左から右、レーンが上から下 (= レーンの中に棒と印)
    cards           カードの並びが本体 (= 今週の計画、まとめ)
    board           表 1 枚が本体 (= 毎週積み上げる早見表)
    agenda          目次 (= 左に全項目、右にバケット。今いる章を強調する)

⚠ **絵を持たなくてよいのは後ろの 3 つだけ。**本文の頁がここを外せるようになると、
「表と文章だけ」の頁が戻ってくる (= 実際にそれで作った頁は全部差し戻された)。
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Callable, Iterable

from .geometry import Rect
from .page import TONES, Card, Page, PageFullError
from .tokens import DEFAULT, Theme

#: A page type fills the area left for the body, and returns nothing.
Filler = Callable[[Page, "Spec", Rect], None]

#: 枠の宣言 (= 書かなければその帯は取られない)
FRAME_KEYS = frozenset({"type", "kind", "title", "kicker", "condition", "conclusion",
                        "footer", "replace"})
#: 本体に添えられるもの (= **どの型でも**読まれる。共通の処理が拾う)
#: ⚠ **カードの列数は `card_columns`。**絵の格子の `columns` と同じ名前だった間は、
#: 格子を 3 列にするとカードまで 3 枚ずつに割れ、格子以外の型ではカードの列数を書けなかった。
EXTRA_KEYS = frozenset({"cards", "card_columns", "table", "note", "points"})

_TYPES: dict[str, tuple[Filler, frozenset, bool]] = {}


class PageTypeError(ValueError):
    """The declaration does not describe a page any type can build."""


@dataclass(frozen=True)
class Spec:
    """One declared page, plus the two things it needs from outside.

    `asset` と `aspect` を渡してもらうのは、頁の層が外の path も画像の中身も
    知らないまま保つため (= 座標が在るのはこの層だけ、という境界と同じ理由)。
    """

    data: dict
    asset: Callable[[str], Path]
    aspect: Callable[[Path], float]

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def text(self, key: str, default: str = "") -> str:
        value = self.data.get(key, default)
        return "" if value is None else str(value)

    def figure(self, key: str = "figure") -> tuple[Path, float]:
        """An image by name, with the aspect ratio read off the file itself.

        ⚠ **縦横比を宣言に書かせない。**手で書くと、絵を差し替えた日に古い比が残って
        潰れた絵が焼ける (= 前の世代で実際に起きた)。
        """
        path = self.asset(str(self.data[key]))
        return path, self.aspect(path)

    def figures(self, key: str = "figures") -> list[tuple[Path, float, str]]:
        """Several images, each with its own caption (= `"name.png"` or `[name, caption]`)."""
        out = []
        for item in self.data[key]:
            if isinstance(item, (list, tuple)):
                name, caption = (list(item) + [""])[:2]
            else:
                name, caption = item, ""
            path = self.asset(str(name))
            out.append((path, self.aspect(path), str(caption)))
        return out

    def rows(self, key: str = "table") -> list[list[str]]:
        return [[str(cell) for cell in row] for row in self.data[key]]

    def cards(self) -> list[Card]:
        return [_card(self, item, f"cards: card {number}")
                for number, item in enumerate(self.data["cards"], start=1)]


def register(name: str, *, needs: Iterable[str], takes: Iterable[str] = (),
             figure: bool = True) -> Callable[[Filler], Filler]:
    """Declare a page type: what its body needs, what else it reads, and whether it shows a picture.

    ⚠ **`takes` は「この型が読む任意のキー」。**共通の付属 (= `EXTRA_KEYS`) と違って、
    読むのは宣言した型だけ ― 読まない型に書けるままだと、書いた人は書いたつもりで、
    焼いた頁にはそれが無い。実際に `figures` の頁で `caption` を黙って落としていた。
    """
    def decorate(filler: Filler) -> Filler:
        _TYPES[name] = (filler, frozenset(needs), frozenset(takes), figure)
        return filler
    return decorate


def names() -> list[str]:
    """Every type a page may ask for."""
    return sorted(_TYPES)


def skeleton() -> list[str]:
    """The types allowed to carry no figure (= the deck's own scaffolding)."""
    return sorted(name for name, spec in _TYPES.items() if not spec[3])


def build(data: dict, asset: Callable[[str], Path], aspect: Callable[[Path], float],
          theme: Theme = DEFAULT) -> Page:
    """Turn one declaration into a page, refusing anything no type can hold."""
    name = str(data.get("type", "")).strip()
    if name not in _TYPES:
        raise PageTypeError(
            f"unknown page type {name!r} — the deck may use only: {', '.join(names())}. "
            "A page that fits none of them means a type is missing; add one rather than "
            "placing shapes by hand."
        )
    filler, needs, takes, wants_figure = _TYPES[name]
    _check_keys(name, data, needs, takes)

    title = data.get("title")
    if not title:
        raise PageTypeError(f"{name}: `title` is missing — every page says what it is")

    page = Page(
        str(title), theme,
        kicker=str(data.get("kicker", "")),
        condition=str(data.get("condition", "")),
        conclusion=str(data.get("conclusion", "")),
        footer=str(data.get("footer", "")),
        needs_figure=wants_figure,
    )
    spec = Spec(data, asset, aspect)
    area = _place_cards(page, spec, page.body)
    area, trailing = _reserve_trailing(page, spec, area)
    filler(page, spec, area)
    _place_trailing(page, spec, trailing)
    return page


def _check_keys(name: str, data: dict, needs: frozenset,
                takes: frozenset = frozenset()) -> None:
    """Refuse a missing key and an unknown one alike.

    ⚠ **知らないキーを黙って捨てない。**綴り違いを捨てると、書いた人は書いたつもりで、
    焼いた頁にはそれが無い ― 前の世代で「値を変えても動かない」を 2 度踏んだ。
    """
    missing = sorted(needs - data.keys())
    if missing:
        raise PageTypeError(
            f"{name}: missing {', '.join(missing)} — this type is not that page without it"
        )
    unknown = sorted(data.keys() - needs - takes - EXTRA_KEYS - FRAME_KEYS)
    if unknown:
        allowed = ", ".join(sorted(needs | takes | EXTRA_KEYS | FRAME_KEYS))
        raise PageTypeError(
            f"{name}: does not take {', '.join(unknown)} (= it accepts {allowed}). "
            "A key nobody reads is a change that silently never happened."
        )


# -- what any page may add around its body ---------------------------------


def _place_cards(page: Page, spec: Spec, area: Rect) -> Rect:
    """Cards above the body, only as tall as their own words."""
    if spec.get("cards") is None:
        return area
    cards = spec.cards()
    if not cards:
        raise PageTypeError("cards: the list is empty")
    columns = int(spec.get("card_columns", len(cards)))
    if columns < 1:
        raise PageTypeError("`card_columns` must be at least 1")
    lines = -(-len(cards) // columns)
    tall = _card_height(page, cards, area.width, columns)
    wanted = tall * lines + page.theme.spacing.gap_m * (lines - 1)
    if wanted >= area.height:
        raise PageFullError(
            f"the cards alone need {wanted} EMU and the body has {area.height} — "
            "fewer cards, or shorter ones; they will not shrink"
        )
    band, rest = area.split_top(wanted, gap=page.theme.spacing.gap_m)
    for index, row in enumerate(band.rows(lines, gap=page.theme.spacing.gap_m)):
        page.boxes(row, cards[index * columns:(index + 1) * columns])
    return rest


def _reserve_trailing(page: Page, spec: Spec, area: Rect) -> tuple[Rect, Rect | None]:
    """Keep room under the body for the table and the reading.

    ⚠ **表の高さは折り返しを勘定して測る。**行数だけで見積もっていた間は、長いラベルが
    2 段に折り返したぶん表が伸び、下に置いたはずの読み方を飲み込んだ。
    """
    reserve = 0
    if spec.get("table") is not None:
        rows = spec.rows()
        widths = page.theme.column_widths(rows, area.width)
        reserve += page.theme.table_height(rows, widths) + page.theme.spacing.gap_m
    for key, size in (("points", None), ("note", None)):
        if spec.text(key):
            reserve += page.theme.text_height(spec.text(key), area.width, size) \
                + page.theme.spacing.gap_s
    if not reserve:
        return area, None
    if reserve >= area.height:
        raise PageFullError(
            f"the table and the reading need {reserve} EMU and the body has "
            f"{area.height} — this is two pages, not one"
        )
    body, _rest = area.split_top(area.height - reserve, gap=page.theme.spacing.gap_m)
    return body, area


def _place_trailing(page: Page, spec: Spec, area: Rect | None) -> None:
    """Put the table and the reading under whatever the body actually used."""
    if area is None:
        return
    used = max((element.rect.bottom for element in page.elements
                if area.top <= element.rect.top <= area.bottom), default=area.top)
    rest = Rect(area.left, used + page.theme.spacing.gap_m, area.width,
                max(area.bottom - used - page.theme.spacing.gap_m, 1))
    if spec.get("table") is not None:
        placed = page.table(rest, spec.rows())
        rest = Rect(rest.left, placed.bottom + page.theme.spacing.gap_s, rest.width,
                    max(rest.bottom - placed.bottom - page.theme.spacing.gap_s, 1))
    note = spec.text("note")
    if spec.get("points"):
        lines = ([line for line in spec.text("points").split("\n") if line.strip()]
                 if isinstance(spec.get("points"), str)
                 else [str(x) for x in spec.get("points")])
        # 読み方のぶんを先に除けてから要点を置く (= 足りないときに読み方が要点の上に
        # 重なるのを防ぐ。どちらも同じ「本体の下」を分け合う)
        kept = (page.theme.text_height(note, rest.width) + page.theme.spacing.gap_s
                if note else 0)
        tall = page.theme.text_height("\n".join(lines), rest.width)
        block, rest = rest.split_top(min(tall, max(rest.height - kept, 1)),
                                     gap=page.theme.spacing.gap_s)
        page.points(block, lines)
    if note:
        page.note(rest, note)


def _card_height(page: Page, cards, width: int, columns: int) -> int:
    """How tall the tallest card has to be for its own words.

    ⚠ **カードに頁の高さを配らない** ― 3 行のカードが 12cm の枠に入ると、字のうしろに
    その差ぶんの空きが残る (= 焼いて初めて出た)。

    ⚠ **行数は箱が実際に折る数で数える** (= `wraps`)。全角 1 文字ぶんで数えていた間は、
    英数字の短い見出しが 2 行と数えられ、箱の中に 1 行ぶんの空白ができた。
    """
    s, ty = page.theme.spacing, page.theme.type
    columns = max(columns, 1)
    column = (width - s.gap_m * (columns - 1)) // columns
    inner = max(column - 2 * s.pad - 2 * s.text_inset, 1)   # 文字が使える幅
    tallest = 0
    for card in cards:
        # アイコンの在る箱は、文字がアイコンの右に寄るぶん狭く、アイコンより低くはならない
        room = max(inner - (s.icon + s.gap_s if card.icon else 0), 1)
        tall = page.theme.wrapped_height(card.heading, room, ty.heading, bold=True)
        if card.body:
            tall += s.gap_s + page.theme.wrapped_height(card.body, room, ty.body)
        tallest = max(tallest, tall, s.icon if card.icon else 0)
    return tallest + 2 * s.pad


# -- the bodies --------------------------------------------------------------


@register("figure", needs=["figure"], takes=["caption"])
def _figure(page: Page, spec: Spec, area: Rect) -> None:
    """One image holding the body."""
    source, aspect = spec.figure()
    page.figure(area, source, aspect, caption=spec.text("caption"))


@register("figures", needs=["figures"])
def _figures(page: Page, spec: Spec, area: Rect) -> None:
    """Images side by side — the shape for comparing conditions."""
    items = spec.figures()
    if len(items) < 2:
        raise PageTypeError("figures: put at least two images side by side, or use `figure`")
    for cell, (source, aspect, caption) in zip(
            area.columns(len(items), gap=page.theme.spacing.gap_m), items):
        page.figure(cell, source, aspect, caption=caption)


@register("figure_grid", needs=["figures"], takes=["columns"])
def _figure_grid(page: Page, spec: Spec, area: Rect) -> None:
    """Images on a grid — two axes at once (= item × method)."""
    items = spec.figures()
    columns = int(spec.get("columns", 3))
    if columns < 1:
        raise PageTypeError("figure_grid: `columns` must be at least 1")
    rows = -(-len(items) // columns)
    cells = [cell for band in area.grid(rows, columns, gap=page.theme.spacing.gap_s)
             for cell in band]
    for cell, (source, aspect, caption) in zip(cells, items):
        page.figure(cell, source, aspect, caption=caption)


def _keys(item, allowed: set, what: str, hint: str = "") -> None:
    """Refuse a key nobody reads inside a type's own tables, the way a page's keys are."""
    if not isinstance(item, dict):
        raise PageTypeError(f"{what} is {item!r} — write it as a table of keys")
    unknown = sorted(item.keys() - allowed)
    if unknown:
        raise PageTypeError(
            f"{what} does not take {', '.join(unknown)} (= it accepts "
            f"{', '.join(sorted(allowed))}).{hint}")


def _tone(item: dict, what: str, unsaid: str) -> str:
    """The tone a table asks for (= one of the palette's roles), or `unsaid` when it asks for none."""
    tone = str(item.get("tone", unsaid))
    if tone not in TONES:
        raise PageTypeError(
            f"{what} has tone {tone!r} — a tone is one of the palette's roles: {', '.join(TONES)}")
    return tone


#: アイコンに読める絵 (= 図と同じ。SVG は pptx に入れるのに描き直しの道具が要るので、まだ読まない)
ICON_FORMATS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff")


def _card(spec: Spec, item, what: str) -> Card:
    """One card, or one node of a flow or a roadmap (= the same box, written the same two ways).

    書き方は 2 つ ― `["見出し", "本文"]` か、色の役やアイコンを付けるときの
    `{ heading = "…", body = "…", tone = "accent", icon = "device.png" }`。
    """
    if isinstance(item, dict):
        _keys(item, {"heading", "body", "tone", "icon"}, what)
        if not str(item.get("heading", "")).strip():
            raise PageTypeError(f"{what} has no `heading` — a box says what it is")
        return Card(str(item["heading"]), str(item.get("body", "")), _tone(item, what, TONES[0]),
                    _icon(spec, item, what))
    if isinstance(item, (list, tuple)) and len(item) == 2:
        return Card(str(item[0]), str(item[1]))
    raise PageTypeError(
        f"{what} is {item!r} — write it as [\"heading\", \"body\"], or as a table "
        "{ heading = …, body = …, tone = …, icon = … }")


def _icon(spec: Spec, item: dict, what: str) -> tuple[Path, float] | None:
    """The picture a box carries beside its words, read like any figure (= from the assets)."""
    if "icon" not in item:
        return None
    name = str(item["icon"])
    if Path(name).suffix.lower() not in ICON_FORMATS:
        raise PageTypeError(
            f"{what} has the icon {name!r} — an icon is a picture file "
            f"({' / '.join(ICON_FORMATS)}); export an SVG as PNG, at a few times the size it "
            "is shown")
    path = spec.asset(name)
    return path, spec.aspect(path)


def _stacks(page: Page, spec: Spec, stages: list, wide: int, aligned: bool,
            what: str) -> tuple[list[list[tuple[Card, int]]], int]:
    """Each stage's nodes with the height each takes, and how tall the tallest stage stands.

    流れ図と道のりが同じ数え方で積む (= 段の下のノードは、どちらでも同じ箱)。
    """
    gap = page.theme.spacing.gap_s
    stacks = []
    for number, stage in enumerate(stages, start=1):
        nodes = [_card(spec, node, f"{what}: stage {number}, node {index}")
                 for index, node in enumerate(stage.get("nodes", []), start=1)]
        if not nodes:
            raise PageTypeError(f"{what}: stage {stage['name']!r} has no nodes")
        stacks.append([(node, _card_height(page, [node], wide, 1)) for node in nodes])
    if aligned:
        # 行ごとに、その行で一番高いノードへ揃える (= 同じ順番のノードが同じ高さに並ぶ)
        rows = [max(column[index][1] for column in stacks if index < len(column))
                for index in range(max(len(column) for column in stacks))]
        stacks = [[(node, rows[index]) for index, (node, _tall) in enumerate(column)]
                  for column in stacks]
        return stacks, sum(rows) + gap * (len(rows) - 1)
    return stacks, max(sum(tall for _n, tall in column) + gap * (len(column) - 1)
                       for column in stacks)


def _aligned(spec: Spec, what: str) -> bool:
    aligned = spec.get("align_rows", False)
    if not isinstance(aligned, bool):
        raise PageTypeError(f"{what}: `align_rows` is true or false, not {aligned!r}")
    return aligned


def _place_stack(page: Page, body: Rect, column: list[tuple[Card, int]]) -> None:
    for node, height in column:
        cell, body = body.split_top(height, gap=page.theme.spacing.gap_s)
        page.boxes(cell, [node])


@register("flow", needs=["stages"], takes=["align_rows"])
def _flow(page: Page, spec: Spec, area: Rect) -> None:
    """Stages left to right, each holding its nodes, each with what is settled below.

    `align_rows = true` は、同じ順番のノードを段をまたいで横に揃える (= 行が「誰の仕事か」の
    ような意味を持つ頁のため。行の高さはその行で一番高いノードに合わせる)。書かなければ、
    ノードは段ごとに自分の言葉の高さで積まれる。

    ⚠ **段の間の向きは文字で置く** (= `marker`)。矢印のプリセット 1 つで PowerPoint が
    修復を言い出した実例がある。
    """
    stages = spec.get("stages")
    if len(stages) < 2:
        raise PageTypeError("flow: a flow needs at least two stages")
    aligned = _aligned(spec, "flow")

    weights: list[float] = []
    for index in range(len(stages)):
        if index:
            weights.append(0.18)
        weights.append(1.0)
    columns = area.columns(weights, gap=page.theme.spacing.gap_s)

    # ノードの高さは**そのノードの言葉**で決め、段ごとに積む。積んだ高さの最大に全段を
    # 揃えるので、列の下端は揃いながら、1 つしかない段が 2 つ分の空きを抱えることもない。
    gap = page.theme.spacing.gap_s
    wide = columns[0].width
    stacks, stack = _stacks(page, spec, stages, wide, aligned, "flow")
    stage_size = page.theme.type.stage
    head_height = max(page.theme.wrapped_height(str(stage["name"]), wide, stage_size, bold=True)
                      for stage in stages)
    # 段の下の 1 行も頁の中身なので、本文の大きさで置く (= 脚注の大きさにしない)
    settled_height = max(
        (page.theme.wrapped_height(str(stage["settled"]), wide - 2 * page.theme.spacing.text_inset)
         for stage in stages if stage.get("settled")), default=0)
    wanted = head_height + gap + stack + (gap + settled_height if settled_height else 0)
    if wanted > area.height:
        raise PageFullError(
            f"this flow needs {wanted} EMU of height and the body has {area.height} — "
            "shorten the nodes or split the stages across two pages; it will not shrink"
        )

    page.drew_a_diagram()  # 段とノードで組んだ流れ図そのものが、この頁の図解
    for index, (stage, column_nodes) in enumerate(zip(stages, stacks)):
        column = columns[index * 2]
        head, rest = column.split_top(head_height, gap=gap)
        page.stage(head, str(stage["name"]))
        body, after = rest.split_top(stack, gap=gap)
        if index:
            # 向きはノードの並びの高さに置く (= 段の名前の横に浮かせない)
            between = columns[index * 2 - 1]
            page.marker(Rect(between.left, body.top, between.width, body.height), "→")
        _place_stack(page, body, column_nodes)
        if stage.get("settled") and settled_height:
            page.note(after.split_top(settled_height)[0], str(stage["settled"]))


#: 余った高さを棒へ配る上限 (= 棒 1 段の高さに対する比)。頁の下に空きを残さないために配るが、
#: 配り切ると 3 本しか無い線表が頁いっぱいの帯になる (= カードに頁の高さを配らないのと同じ理由)
ROOMY = 1.5


@dataclass
class _Piece:
    """One thing on the time axis: a bar, a mark or a date, with the room its name takes."""

    left: int
    right: int
    text: str
    #: 名前をどこに書くか (= `in` 棒の中 / `right` / `left` 隣)
    side: str
    tall: int
    #: 名前の幅 (= 隣に書くときに取る)
    wide: int = 0
    tentative: bool = False
    point: bool = False
    row: int = 0

    def room(self, gap: int) -> tuple[int, int]:
        """What it keeps clear of its neighbours: itself, and its name when that sits beside it."""
        start = self.left - (gap + self.wide + gap if self.side == "left" else 0)
        end = self.right + (gap + self.wide + gap if self.side == "right" else 0)
        return start, end


def _position(item: dict, key: str, count: int, what: str) -> float:
    """A place on the time axis, given as a period number (= 0 is where the first period starts)."""
    value = item.get(key)
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PageTypeError(
            f"timeline: {what} needs `{key}` as a period number (= 0 is the start of the first "
            f"period, {count} the end of the last; 0.5 is half a period), not {value!r}")
    if not 0 <= value <= count:
        raise PageTypeError(
            f"timeline: {what} has `{key}` = {value:g}, outside the {count} periods (= 0 to {count})")
    return float(value)


def _stretch(item: dict, count: int, what: str) -> tuple[float, float]:
    start, end = _position(item, "from", count, what), _position(item, "to", count, what)
    if end <= start:
        raise PageTypeError(
            f"timeline: {what} runs from {start:g} to {end:g} — it has to end after it starts")
    return start, end


def _reach(bar: dict, left: int, what: str) -> int:
    """How many lanes a bar covers, this one and the ones under it (= `spans`; unsaid, 1)."""
    value = bar.get("spans", 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PageTypeError(
            f"timeline: {what} needs `spans` as a whole number of lanes (= 2 covers this lane "
            f"and the one under it), not {value!r}")
    if value > left:
        raise PageTypeError(
            f"timeline: {what} spans {value} lanes, but only {left} "
            f"{'is' if left == 1 else 'are'} left from its own lane down")
    return value


def _rows(pieces: list[_Piece], gap: int) -> int:
    """Give each piece the first row it clears, left to right, and say how many rows that took."""
    ends: list[int] = []
    for piece in sorted(pieces, key=lambda p: p.room(gap)[0]):
        start, end = piece.room(gap)
        for row, taken in enumerate(ends):
            if taken <= start:
                piece.row, ends[row] = row, end
                break
        else:
            piece.row = len(ends)
            ends.append(end)
    return len(ends)


def _flags(pieces: list[_Piece], gap: int) -> int:
    """Rows for the names of dates that cut across the page, each name flying from its own line.

    線は自分の名前の段から下へ伸びる。だから**名前が、上の段から降りてくる別の線に
    貫かれない**段を選ぶ (= 貫かれると、どの線の名前か読めなくなる)。置ける段が無ければ
    いちばん上に段を足す。
    """
    placed: list[_Piece] = []
    rows = 0

    def clear(piece: _Piece, row: int) -> bool:
        start, end = piece.room(gap)
        for other in placed:
            o_start, o_end = other.room(gap)
            if other.row == row and start < o_end and o_start < end:
                return False                      # 同じ段で名前どうしが重なる
            if other.row < row and start < other.left < end:
                return False                      # 上の段の線が、この名前を貫く
            if other.row > row and o_start < piece.left < o_end:
                return False                      # この線が、下の段の名前を貫く
        return True

    for piece in sorted(pieces, key=lambda p: p.left):
        row = next((r for r in range(rows + 1) if clear(piece, r)), None)
        if row is None:
            for other in placed:
                other.row += 1
            row = 0
            if not clear(piece, row):
                raise PageFullError(
                    f"the milestone {piece.text!r} sits too close to the others for every name "
                    "to be read — fewer milestones here, or shorter names; they will not shrink")
        piece.row = row
        placed.append(piece)
        rows = max(p.row for p in placed) + 1
    return rows


@register("roadmap", needs=["stages"], takes=["align_rows"])
def _roadmap(page: Page, spec: Spec, area: Rect) -> None:
    """The road to a goal: stages left to right as arrowheads, each holding what it delivers.

    段は `name` (= 矢羽根の中。時期と版を「11 月上旬 | 0.4.0」のように書く) と `nodes`
    (= flow と同じ 2 通りの書き方と `tone`、`icon`)。**最後の段だけ** `goal = true` を書ける
    (= 到達点。濃い地で、名前を一回り大きく置く)。`align_rows` は flow と同じ。

    矢羽根は最初の段が左の平らな形、2 段目からが左の切り欠いた形で、先が次の段の切り欠きに
    噛み合う。向きは矢羽根が示すので、段の間に「→」は置かない。
    """
    stages = spec.get("stages") or []
    if len(stages) < 2:
        raise PageTypeError("roadmap: a road needs at least two stages")
    for number, stage in enumerate(stages, start=1):
        what = f"roadmap: stage {number}"
        if not isinstance(stage, dict):
            raise PageTypeError(f"{what} is {stage!r} — write it as a table "
                                "{ name = …, nodes = […], goal = … }")
        _keys(stage, {"name", "nodes", "goal"}, what)
        if not str(stage.get("name", "")).strip():
            raise PageTypeError(f"{what} has no `name` — an arrowhead says when it is")
        goal = stage.get("goal", False)
        if not isinstance(goal, bool):
            raise PageTypeError(f"{what}: `goal` is true or false, not {goal!r}")
        if goal and number != len(stages):
            raise PageTypeError(
                f"{what} is marked as the goal, but the goal is where the road ends — "
                "only the last stage takes `goal = true`")
    aligned = _aligned(spec, "roadmap")
    goal = bool(stages[-1].get("goal"))

    theme, s, ty = page.theme, page.theme.spacing, page.theme.type
    gap = s.gap_s
    columns = area.columns(len(stages), gap=s.gap_m)
    stacks, stack = _stacks(page, spec, stages, columns[0].width, aligned, "roadmap")

    # 矢羽根は自分の列から次の列の頭まで伸び、先が次の段の切り欠きに入る (= 最後の段は列の中で
    # 尖る)。文字が使える幅は、プリセットが決めた文字の枠 (= 切り欠きと先を除いた幅) から余白を引く
    point = s.chevron_point
    arrows, sizes = [], []
    for index, (stage, column) in enumerate(zip(stages, columns)):
        last = index == len(stages) - 1
        right = column.right if last else columns[index + 1].left
        shape = "home" if index == 0 else "chevron"
        cut = point // 2 if shape == "home" else 2 * point     # 文字の枠が左右で失う幅
        room = max(right - column.left - cut - 2 * s.bar_pad_x, 1)
        size = ty.heading if last and goal else ty.stage
        tall = theme.wrapped_height(str(stage["name"]), room, size, bold=True) + 2 * s.bar_pad_y
        arrows.append((Rect(column.left, area.top, right - column.left, 1), shape, size, tall))
    head_height = max(tall for _r, _s, _z, tall in arrows)

    wanted = head_height + gap + stack
    if wanted > area.height:
        raise PageFullError(
            f"this roadmap needs {wanted} EMU of height and the body has {area.height} — "
            "shorten the nodes or split the stages across two pages; it will not shrink")

    page.drew_a_diagram()  # 矢羽根とノードで組んだ道のりそのものが、この頁の図解
    for index, ((rect, shape, size, _tall), stage, column, column_nodes) in enumerate(
            zip(arrows, stages, columns, stacks)):
        last = index == len(stages) - 1
        page.chevron(Rect(rect.left, area.top, rect.width, head_height), str(stage["name"]),
                     shape=shape, tone="accent" if last and goal else "band", size=size)
        _head, rest = column.split_top(head_height, gap=gap)
        _place_stack(page, rest.split_top(stack)[0], column_nodes)


@register("timeline", needs=["periods", "lanes"], takes=["phases", "milestones"])
def _timeline(page: Page, spec: Spec, area: Rect) -> None:
    """Periods left to right, lanes top to bottom, bars and marks on the lanes.

    位置は**期間の番号**で受ける (= 0 が最初の期間の頭、`len(periods)` が最後の期間の終わり、
    半期間なら 0.5)。座標は受け取らない ― 型が `area` を割って決める。

    期間は列ごとに見出しの枠を持ち、列は 1 つおきに薄い地で塗る (= どの棒がどの期間に
    掛かるかを、見出しから下へ目で辿れる)。帯 (`phases`) はその上に、端を期間の枠と揃えて置く。

    レーンの棒の地は、書かなければ 2 つの薄い地の交互。レーンに `tone` を書くとその色の役に
    なる (= `flow` のノードと同じ語彙。3 者を色で分ける、1 本だけ目立たせる)。

    棒は `spans` で下のレーンへまたがれる (= 2 つのレーンに分けた仕事の、共通の時期を 1 本で
    描く)。またがる棒は、覆うレーンの高さを全部取る ― その時期、覆われるレーンには何も
    置けない (= 重なる棒と印は拒む)。色は書いたレーンのもの、名前はいつも棒の中。

    ⚠ **文字は全部 pptx の文字のまま置く。**この型は、絵で描いて貼った計画の頁を人が
    直せなかったために在る。棒の名前は棒の中に持たせ、2 行でも収まらない名前は棒の隣へ
    出す (= 縮めない、切らない)。隣にも置けなければ棒の中で折り返す。

    ⚠ **文字の大きさは `plan` の中から、頁に収まる最初のものを採る** (= 余った高さは文字と
    棒の高さに配る)。いちばん小さいものでも収まらなければ `PageFullError` で止める。

    ⚠ **向きは矢印の図形で描かない** (= `flow` と同じ理由)。順序は棒の並びが示す。
    """
    theme, s = page.theme, page.theme.spacing
    periods = [str(period) for period in spec.get("periods") or []]
    lanes = spec.get("lanes") or []
    if not periods:
        raise PageTypeError("timeline: `periods` is empty — a timeline needs its periods")
    if not lanes:
        raise PageTypeError("timeline: `lanes` is empty — a timeline needs at least one lane")
    count = len(periods)
    misplaced = (" `phases` and `milestones` belong to the page: in TOML, write them above the "
                 "first `[[pages.lanes]]`.")

    # -- 書かれた物を読む (= 位置は文字の大きさに依らないので、1 度だけ) -----------------
    spans = []
    for index, phase in enumerate(spec.get("phases") or [], start=1):
        _keys(phase, {"from", "to", "label"}, f"timeline: phase {index}")
        start, end = _stretch(phase, count, f"phase {index}")
        spans.append((start, end, str(phase.get("label", ""))))
    spans.sort()
    for (_s, before, _l), (after, _e, label) in zip(spans, spans[1:]):
        if after < before:
            raise PageTypeError(f"timeline: phase {label!r} starts before the one before it ends")
    dates = []
    for index, stone in enumerate(spec.get("milestones") or [], start=1):
        _keys(stone, {"at", "text"}, f"timeline: milestone {index}")
        dates.append((_position(stone, "at", count, f"milestone {index}"), str(stone.get("text", ""))))
    read = []
    # レーンごとの、またがる棒が覆う時期 (= そのレーンから出る棒と、上のレーンから降りてくる棒)
    covered: list[list[tuple[float, float, str]]] = [[] for _lane in lanes]
    for index, lane in enumerate(lanes, start=1):
        _keys(lane, {"name", "bars", "marks", "tone"}, f"timeline: lane {index}", misplaced)
        bars, marks = [], []
        for number, bar in enumerate(lane.get("bars") or [], start=1):
            what = f"lane {index}, bar {number}"
            _keys(bar, {"from", "to", "text", "tentative", "spans"}, f"timeline: {what}")
            start, end = _stretch(bar, count, what)
            reach = _reach(bar, len(lanes) - index + 1, what)
            bars.append((what, start, end, str(bar.get("text", "")), bool(bar.get("tentative")), reach))
            if reach > 1:
                for under in range(index - 1, index - 1 + reach):
                    covered[under].append((start, end, what))
        for number, mark in enumerate(lane.get("marks") or [], start=1):
            what = f"lane {index}, mark {number}"
            _keys(mark, {"at", "text"}, f"timeline: {what}")
            marks.append((what, _position(mark, "at", count, what), str(mark.get("text", ""))))
        # 色の役を書いたレーンはその色、書かなければ 2 つの薄い地の交互 (= 隣と見分けるだけ)
        tone = _tone(lane, f"timeline: lane {index}", TONES[(index - 1) % 2])
        read.append((str(lane.get("name", "")), tone, bars, marks))

    # またがる棒は覆うレーンの高さを全部取る。その時期に同じレーンへ置かれた物は、段を分けて
    # 逃がせない (= 重ねて描くことになる) ので、読んだ時点で拒む
    for index, ((_name, _tone_, bars, marks), walls) in enumerate(zip(read, covered), start=1):
        if not bars and not marks and not walls:
            raise PageTypeError(f"timeline: lane {index} has neither bars nor marks")
        for number, (start, end, what) in enumerate(walls):
            for other_start, other_end, other in walls[number + 1:]:
                if start < other_end and other_start < end:
                    raise PageTypeError(
                        f"timeline: {what} and {other} both span lane {index} over the same "
                        "periods — a lane holds one spanning bar at a time")
            for other, other_start, other_end, _text, _tentative, reach in bars:
                if reach == 1 and start < other_end and other_start < end:
                    raise PageTypeError(
                        f"timeline: {other} runs under {what}, which spans lane {index} from "
                        f"{start:g} to {end:g} — a spanning bar takes the whole lane; end one "
                        "where the other starts")
            for other, position, _text in marks:
                if start <= position <= end:
                    raise PageTypeError(
                        f"timeline: {other} sits on {what}, which spans lane {index} from "
                        f"{start:g} to {end:g} — a spanning bar takes the whole lane; move the "
                        "mark off its periods")

    # 左にレーンの名前、右に時間。名前の列は一番長い名前ぶんで、取りすぎるなら折り返させる。
    # 時間の側は印の半分だけ内へ寄せる (= 端の時点に置いた印が枠から出ない)
    lane_size = theme.type.stage
    widest = max(theme.width(name, lane_size, bold=True) for name, _t, _b, _m in read)
    name_width = min(widest + s.gap_s, area.width // 4)
    names, column = area.columns([name_width, area.width - name_width], gap=s.gap_s)
    plot = column.inset(x=s.mark // 2)

    def at(position: float) -> int:
        return plot.span(0, position / count).right

    crossing = [at(position) for position, _text in dates]   # 頁を横切る日付の線の位置

    def beside(left: int, right: int, wide: int, walls=()) -> str | None:
        """Which side of something a name of this width can go on, if either.

        右が先。ただし日付の線が名前を貫く側は、貫かれない側が在ればそちらへ譲る。
        `walls` はそのレーンを覆うまたがる棒の左右 ― 名前はその上へは出せない。
        """
        fits = []
        if right + s.gap_s + wide <= column.right:
            fits.append(("right", right + s.gap_s, right + s.gap_s + wide))
        if left - s.gap_s - wide >= column.left:
            fits.append(("left", left - s.gap_s - wide, left - s.gap_s))
        fits = [(side, start, end) for side, start, end in fits
                if not any(start < wall_right + s.gap_s and wall_left - s.gap_s < end
                           for wall_left, wall_right in walls)]
        clear = [side for side, start, end in fits if not any(start < x < end for x in crossing)]
        return (clear or [side for side, _start, _end in fits] or [None])[0]

    def laid(size: float):
        """Everything measured at one type size, or PageFullError when the page cannot hold it."""
        line = theme.line_height(size)
        cell = line + 2 * s.bar_pad_y          # 棒 1 段・期間の枠 1 つの高さ

        span_height = 0
        for start, end, label in spans:
            inner = at(end) - at(start) - 2 * (s.bar_gap + s.bar_pad_x)
            span_height = max(span_height, theme.wrapped_height(label, max(inner, 1), size)
                              + 2 * s.bar_pad_y)
        for index, period in enumerate(periods):
            inner = at(index + 1) - at(index) - 2 * (s.bar_gap + s.bar_pad_x)
            if theme.width(period, size, bold=True) > inner:
                raise PageFullError(
                    f"the period name {period!r} is wider than one of {count} columns at "
                    f"{size:g}pt — shorter names, or fewer periods on this page; it will not shrink")

        stones = []
        for where, text in zip(crossing, (text for _p, text in dates)):
            wide = theme.width(text, size, bold=True)
            side = beside(where, where, wide)
            if side is None:
                raise PageFullError(f"the milestone name {text!r} is wider than the timeline itself")
            stones.append(_Piece(where, where, text, side, line, wide))
        stone_rows = _flags(stones, s.bar_pad_x)

        packed = []
        across = []                            # またがる棒 (= 出るレーンの番号, 覆うレーンの数, 棒)
        for lane, ((name, tone, bars, marks), covering) in enumerate(zip(read, covered)):
            walls = [(at(start) + s.bar_gap, at(end) - s.bar_gap) for start, end, _what in covering]
            pieces = []
            for what, start, end, text, tentative, reach in bars:
                left, right = at(start) + s.bar_gap, at(end) - s.bar_gap
                if right <= left:
                    raise PageFullError(f"{what} is too short a stretch to draw at this scale")
                wide, inner = theme.width(text, size), right - left - 2 * s.bar_pad_x
                if reach > 1:
                    # 名前はいつも棒の中 (= 隣へ出すと、覆うレーン全部でその場所を空けることになる)。
                    # 棒が高いので、折れる行は中に収まる
                    lines = 1 if wide <= inner else theme.wraps(text, max(inner, 1), size)
                    across.append((lane, reach, _Piece(left, right, text, "in",
                                                       lines * line + 2 * s.bar_pad_y, wide,
                                                       tentative=tentative)))
                    continue
                if wide <= inner:
                    side, lines = "in", 1
                elif theme.unbreakable(text, size) <= inner and theme.wraps(text, inner, size) == 2:
                    side, lines = "in", 2      # 語の切れ目で 2 行に収まる (= 語の途中では折らない)
                elif beside(left, right, wide, walls):
                    side, lines = beside(left, right, wide, walls), 1
                else:
                    side, lines = "in", theme.wraps(text, max(inner, 1), size)
                pieces.append(_Piece(left, right, text, side, lines * line + 2 * s.bar_pad_y, wide,
                                     tentative=tentative))
            for what, position, text in marks:
                where = at(position)
                left, right = where - s.mark // 2, where - s.mark // 2 + s.mark
                wide = theme.width(text, size)
                side = beside(left, right, wide, walls)
                if side is None and beside(left, right, wide) is not None:
                    raise PageFullError(
                        f"the name of {what} ({text!r}) has no room beside it: a bar spanning "
                        "this lane stands on either side it could go — a shorter name, or move "
                        "the mark; it will not shrink")
                if side is None:
                    raise PageFullError(
                        f"the name of {what} ({text!r}) is wider than the timeline itself")
                pieces.append(_Piece(left, right, text, side, max(s.mark, cell), wide, point=True))
            name_tall = theme.wrapped_height(name, names.width, lane_size, bold=True)
            rows = _rows(pieces, s.gap_s)
            # 自分の物を持たないレーン (= 上から降りてくる棒に覆われるだけ) も 1 段ぶんは取る
            heights = [max(p.tall for p in pieces if p.row == row) for row in range(rows)] or [cell]
            packed.append((name, name_tall, pieces, heights, tone))

        # またがる棒の名前が、覆うレーンを合わせた高さに収まらなければ、出るレーンの 1 段目を
        # そのぶん高くする (= 縮めない、切らない)
        for lane, reach, piece in across:
            top, bottom = reaches(packed, lane, lane + reach - 1)
            if piece.tall > bottom - top:
                packed[lane][3][0] += piece.tall - (bottom - top)

        head = (span_height + s.row_gap if spans else 0) + cell + s.gap_s \
            + (stone_rows * line + s.gap_s if stones else 0)
        wanted = head + sum(lane_height(name_tall, heights) for _n, name_tall, _p, heights, _t in packed)
        if wanted > area.height:
            raise PageFullError(
                f"this timeline needs {wanted} EMU of height at {size:g}pt and the body has "
                f"{area.height} — fewer lanes, shorter names, or two pages; it will not shrink")
        return size, line, cell, span_height, stones, stone_rows, packed, across, wanted

    def lane_height(name_tall: int, heights: list[int], extra: int = 0) -> int:
        # レーンの上下の余白は段の間と同じ幅 (= 区切りの線が在るので、広く空けなくても分かれる。
        # 広く取ると、文字を大きくしたぶん載るレーンが減る)
        stack = sum(tall + extra for tall in heights) + s.row_gap * (len(heights) - 1)
        return max(stack, name_tall) + 2 * s.row_gap

    def reaches(packed: list, first: int, last: int, extra: int = 0, top: int = 0) -> tuple[int, int]:
        """From the top of lane `first`'s first row to the bottom of lane `last`'s last row.

        `top` はレーンの並びの上端 (= 測るだけなら 0 でよい。置くときは最初のレーンの上端)。
        """
        starts = [top]
        for _name, name_tall, _pieces, heights, _tone_ in packed:
            starts.append(starts[-1] + lane_height(name_tall, heights, extra))
        heights = packed[last][3]
        stack = sum(tall + extra for tall in heights) + s.row_gap * (len(heights) - 1)
        return starts[first] + s.row_gap, starts[last] + s.row_gap + stack

    # 大きい文字から試し、頁に収まる最初の大きさで組む (= 余った高さは文字に配る)
    for size in theme.type.plan:
        try:
            size, line, cell, span_height, stones, stone_rows, packed, across, wanted = laid(size)
            break
        except PageFullError as full:
            refused = full
    else:
        raise refused
    extra = min((area.height - wanted) // sum(len(heights) for _n, _t, _p, heights, _tone_ in packed),
                round(cell * ROOMY))

    # -- 置く (= 上から帯を取り、その中を割る) -------------------------------------
    page.drew_a_diagram()  # レーンと棒で組んだ線表そのものが、この頁の図解
    rest = area
    span_band = None
    if spans:
        span_band, rest = rest.split_top(span_height, gap=s.row_gap)
    period_band, rest = rest.split_top(cell, gap=s.gap_s)
    flags_top = rest.top
    if stones:
        _band, rest = rest.split_top(stone_rows * line, gap=s.gap_s)
    bands = []
    for _name, name_tall, _pieces, heights, _lane_tone in packed:
        band, rest = rest.split_top(lane_height(name_tall, heights, extra))
        bands.append(band)
    lanes_top, lanes_bottom = bands[0].top, bands[-1].bottom

    # 下に敷く物から先に置く: 列の地 → 期間の境 → レーンの区切り → 頁を横切る日付の線
    # (= 線を棒の上に引くと、棒の名前を貫く)
    for index in range(1, count, 2):
        page.stripe(Rect(at(index), period_band.bottom, at(index + 1) - at(index),
                         lanes_bottom - period_band.bottom))
    for index in range(count + 1):
        page.rule(Rect(at(index) - s.hairline // 2, period_band.bottom, s.hairline,
                       lanes_bottom - period_band.bottom), weight="firm")
    for edge in [band.top for band in bands] + [lanes_bottom - s.hairline]:
        page.rule(Rect(area.left, edge, area.width, s.hairline))
    for stone in stones:
        top = flags_top + stone.row * line
        page.rule(Rect(stone.left - s.hairline, top, 2 * s.hairline, lanes_bottom - top),
                  weight="strong")

    def over(band: Rect, start: float, end: float) -> Rect:
        """The part of a band over a stretch of periods, drawn in by the gap bars keep."""
        return Rect(plot.left, band.top, plot.width, band.height) \
            .span(start / count, end / count).inset(x=s.bar_gap)

    for start, end, label in spans:
        page.span(over(span_band, start, end), label, size=size)
    for index, period in enumerate(periods):
        page.period(over(period_band, index, index + 1), period, size=size)

    for band, (name, _name_tall, pieces, heights, tone) in zip(bands, packed):
        inner = band.inset(y=s.row_gap)
        page.lane(Rect(names.left, inner.top, names.width, inner.height), name)
        tops = [inner.top]
        for tall in heights:
            tops.append(tops[-1] + tall + extra + s.row_gap)
        for piece in pieces:
            top, tall = tops[piece.row], heights[piece.row] + extra
            if piece.point:
                page.diamond(Rect(piece.left, top + (tall - s.mark) // 2, s.mark, s.mark))
            else:
                page.bar(Rect(piece.left, top, piece.right - piece.left, tall),
                         piece.text if piece.side == "in" else "",
                         tone=tone, tentative=piece.tentative, size=size)
            if piece.side == "right":
                page.label(Rect(piece.right + s.gap_s, top, piece.wide, tall), piece.text, size=size)
            elif piece.side == "left":
                page.label(Rect(piece.left - s.gap_s - piece.wide, top, piece.wide, tall),
                           piece.text, align="right", size=size)

    # またがる棒は区切りの線の上に置く (= 覆うレーンの間の線を棒が隠し、1 本に見える)
    for lane, reach, piece in across:
        top, bottom = reaches(packed, lane, lane + reach - 1, extra, lanes_top)
        page.bar(Rect(piece.left, top, piece.right - piece.left, bottom - top), piece.text,
                 tone=packed[lane][4], tentative=piece.tentative, size=size)

    for stone in stones:
        top = flags_top + stone.row * line
        if stone.side == "right":
            page.label(Rect(stone.left + s.bar_pad_x, top, stone.wide, line), stone.text,
                       role="accent", size=size)
        else:
            page.label(Rect(stone.left - s.bar_pad_x - stone.wide, top, stone.wide, line),
                       stone.text, align="right", role="accent", size=size)


@register("cards", needs=[], figure=False)
def _cards(page: Page, spec: Spec, area: Rect) -> None:
    """The cards are the page (= this week's plan, what a chapter concluded).

    カードは全型が添えられるので、この型の本体は空でよい ― `cards` を本体として
    置いた時点で、もう頁は組み上がっている。
    """
    if spec.get("cards") is None:
        raise PageTypeError("cards: this type is the cards; give it some")


@register("board", needs=["table"], figure=False)
def _board(page: Page, spec: Spec, area: Rect) -> None:
    """One table using the page (= the figures are the numbers).

    ⚠ **これは例外の型。**「表と文章だけの頁を出さない」の唯一の抜け道で、毎週
    積み上げる早見表のためにある (= 頁の面積は数字に使い、説明は指標の頁が持つ)。
    本文の頁をここに逃がさない。
    """


@register("agenda", needs=["buckets"], takes=["highlight"], figure=False)
def _agenda(page: Page, spec: Spec, area: Rect) -> None:
    """Every item on the left, the buckets on the right, this chapter marked.

    進行型の目次 (= 章の頭ごとに 1 枚置き、その章だけを強調する)。⚠ **実頁の無い
    小項目を書かない** ― 目次に残すと翌週がそれを輸入して持ち越す。
    """
    buckets = [(str(title), [str(item) for item in items])
               for title, items in spec.get("buckets")]
    if not buckets:
        raise PageTypeError("agenda: `buckets` is empty — an agenda with no chapters")
    here = int(spec.get("highlight", 0))
    if here and not 1 <= here <= len(buckets):
        raise PageTypeError(
            f"agenda: `highlight` is {here}, but there are {len(buckets)} buckets"
        )
    listing, right = area.columns([1, 1], gap=page.theme.spacing.gap_l)
    lines: list[str] = []
    for title, items in buckets:
        lines.append(title)
        lines.extend(f"    {item}" for item in items)
    page.points(listing, lines)
    for band, (number, (title, _items)) in zip(
            right.rows(len(buckets), gap=page.theme.spacing.gap_m),
            enumerate(buckets, start=1)):
        head = f"{number}. {title}"
        mark = "◀ この章" if number == here else ""
        tall = _card_height(page, [Card(head, mark)], band.width, 1)
        cell, _rest = band.split_top(min(tall, band.height))
        page.boxes(cell, [Card(head, mark)])


def describe() -> str:
    """Every type and the keys each reads, from the registry itself (= never out of date)."""
    lines = ["page types (kind = \"declare\"):"]
    for name in names():
        _filler, needs, takes, figure = _TYPES[name]
        needed = ", ".join(sorted(needs)) or "—"
        own = ", ".join(sorted(takes)) or "—"
        lines.append(f"  {name:<12} needs: {needed:<10} also reads: {own:<10}"
                     f"{'' if figure else '  (may carry no picture)'}")
    lines.append(f"  on any type: {', '.join(sorted(EXTRA_KEYS))}")
    lines.append(f"  the frame:   {', '.join(sorted(FRAME_KEYS - {'type', 'kind'}))}")
    return "\n".join(lines)
