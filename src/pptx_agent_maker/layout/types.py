"""The finite set of page shapes a deck may use.

**型を用意して「使ってください」にすると、使われない。**前の世代では版面の縦位置を
いくつか名前で持っていたが、頁は隣に自分の値を書き、名前のある位置のすぐ横に
名前のない値が積み上がった。読み手には、0.3mm のずれが重なった揺れとして届く。

ここでは頁が**型を選ぶことしかできない**。座標を書く口も、並びを変える口も無い。

版面の並びは 1 つしかない。書かなかった帯は取られないだけで、順序は動かない:

    題 → 条件の帯 → カード → **本体** → 表 → 読み方 → 結論の帯 → 出所

型が決めるのは**本体に何をどう置くか**だけで、カード・表・読み方・要点はどの型でも
添えられる。既に組まれたデッキ群を数えると、頁の中身は「絵が 1 枚か / 並ぶか / 無いか」
と「表と文を添えるか」でほとんど尽きていた ― 本体の形を型に、それ以外を付属にすると、
型はこの 7 つで足りる。

    figure          絵 1 枚が本体
    figures         絵を横に並べる (= 条件ちがいの比較)
    figure_grid     絵を格子に並べる (= 対象 × 条件のような 2 軸)
    flow            段が左から右へ流れる (= 各段にノード、段の下に分かったこと)
    cards           カードの並びが本体 (= 今週の計画、まとめ)
    board           表 1 枚が本体 (= 毎週積み上げる早見表)
    agenda          目次 (= 左に全項目、右にバケット。今いる章を強調する)

⚠ **絵を持たなくてよいのは後ろの 3 つだけ。**本文の頁がここを外せるようになると、
「表と文章だけ」の頁が戻ってくる (= 実際にそれで作った頁は全部差し戻された)。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .geometry import Rect
from .page import Page, PageFullError
from .tokens import DEFAULT, Theme

#: A page type fills the area left for the body, and returns nothing.
Filler = Callable[[Page, "Spec", Rect], None]

#: 枠の宣言 (= 書かなければその帯は取られない)
FRAME_KEYS = frozenset({"type", "kind", "title", "kicker", "condition", "conclusion",
                        "footer", "replace", "highlight"})
#: 本体に添えられるもの (= どの型でも任意)
EXTRA_KEYS = frozenset({"cards", "table", "note", "points", "caption", "columns"})

_TYPES: dict[str, tuple[Filler, frozenset, bool]] = {}


class PageTypeError(ValueError):
    """The declaration does not describe a page any type can build."""


@dataclass(frozen=True)
class Spec:
    """One declared page, plus the two things it needs from outside.

    `asset` と `aspect` を渡してもらうのは、版面の層が外の path も画像の中身も
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

    def cards(self) -> list[tuple[str, str]]:
        return [(str(head), str(body)) for head, body in self.data["cards"]]


def register(name: str, *, needs: Iterable[str], figure: bool = True
             ) -> Callable[[Filler], Filler]:
    """Declare a page type, what its body needs, and whether it must show a picture."""
    def decorate(filler: Filler) -> Filler:
        _TYPES[name] = (filler, frozenset(needs), figure)
        return filler
    return decorate


def names() -> list[str]:
    """Every type a page may ask for."""
    return sorted(_TYPES)


def skeleton() -> list[str]:
    """The types allowed to carry no figure (= the deck's own scaffolding)."""
    return sorted(name for name, spec in _TYPES.items() if not spec[2])


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
    filler, needs, wants_figure = _TYPES[name]
    _check_keys(name, data, needs)

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


def _check_keys(name: str, data: dict, needs: frozenset) -> None:
    """Refuse a missing key and an unknown one alike.

    ⚠ **知らないキーを黙って捨てない。**綴り違いを捨てると、書いた人は書いたつもりで、
    焼いた頁にはそれが無い ― 前の世代で「値を変えても動かない」を 2 度踏んだ。
    """
    missing = sorted(needs - data.keys())
    if missing:
        raise PageTypeError(
            f"{name}: missing {', '.join(missing)} — this type is not that page without it"
        )
    unknown = sorted(data.keys() - needs - EXTRA_KEYS - FRAME_KEYS)
    if unknown:
        allowed = ", ".join(sorted(needs | EXTRA_KEYS | FRAME_KEYS))
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
    columns = int(spec.get("columns", len(cards)))
    if columns < 1:
        raise PageTypeError("`columns` must be at least 1")
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


def _card_height(page: Page, cards, width: int, columns: int, *, small: bool = False) -> int:
    """How tall the tallest card has to be for its own words.

    ⚠ **カードに頁の高さを配らない** ― 3 行のカードが 12cm の枠に入ると、字のうしろに
    その差ぶんの空きが残る (= 焼いて初めて出た)。
    """
    s, ty = page.theme.spacing, page.theme.type
    columns = max(columns, 1)
    column = (width - s.gap_m * (columns - 1)) // columns
    inner = max(column - 2 * s.pad, 1)
    tallest = 0
    for heading, body in cards:
        tall = page.theme.text_height(heading, inner, ty.heading)
        if body:
            tall += s.gap_s + page.theme.text_height(
                body, inner, ty.caption if small else ty.body)
        tallest = max(tallest, tall)
    return tallest + 2 * s.pad


# -- the seven bodies ------------------------------------------------------


@register("figure", needs=["figure"])
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


@register("figure_grid", needs=["figures"])
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


@register("flow", needs=["stages"])
def _flow(page: Page, spec: Spec, area: Rect) -> None:
    """Stages left to right, each holding its nodes, each with what is settled below.

    ⚠ **段の間の向きは文字で置く** (= `marker`)。矢印のプリセット 1 つで PowerPoint が
    修復を言い出した実例がある。
    """
    stages = spec.get("stages")
    if len(stages) < 2:
        raise PageTypeError("flow: a flow needs at least two stages")

    weights: list[float] = []
    for index in range(len(stages)):
        if index:
            weights.append(0.18)
        weights.append(1.0)
    columns = area.columns(weights, gap=page.theme.spacing.gap_s)

    # ノードの高さは**そのノードの言葉**で決め、段ごとに積む。積んだ高さの最大に全段を
    # 揃えるので、列の下端は揃いながら、1 つしかない段が 2 つ分の空きを抱えることもない。
    gap = page.theme.spacing.gap_s
    stacks = []
    for stage in stages:
        nodes = [(str(a), str(b)) for a, b in stage.get("nodes", [])]
        if not nodes:
            raise PageTypeError(f"flow: stage {stage['name']!r} has no nodes")
        stacks.append([(node, _card_height(page, [node], columns[0].width, 1, small=True))
                       for node in nodes])
    head_height = page.theme.line_height(page.theme.type.caption)
    settled_height = max(
        (page.theme.text_height(str(stage["settled"]), columns[0].width,
                                page.theme.type.caption)
         for stage in stages if stage.get("settled")), default=0)
    stack = max(sum(h for _n, h in column) + gap * (len(column) - 1) for column in stacks)
    wanted = head_height + gap + stack + (gap + settled_height if settled_height else 0)
    if wanted > area.height:
        raise PageFullError(
            f"this flow needs {wanted} EMU of height and the body has {area.height} — "
            "shorten the nodes or split the stages across two pages; it will not shrink"
        )

    page.drew_a_diagram()  # 段とノードで組んだ流れ図そのものが、この頁の図解
    for index, (stage, column_nodes) in enumerate(zip(stages, stacks)):
        column = columns[index * 2]
        if index:
            page.marker(columns[index * 2 - 1], "→")
        head, rest = column.split_top(head_height, gap=gap)
        page.caption(head, str(stage["name"]))
        body, after = rest.split_top(stack, gap=gap)
        for node, height in column_nodes:
            cell, body = body.split_top(height, gap=gap)
            page.boxes(cell, [node], small=True)
        if stage.get("settled") and settled_height:
            page.caption(after.split_top(settled_height)[0], str(stage["settled"]),
                         align="left")


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


@register("agenda", needs=["buckets"], figure=False)
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
        tall = _card_height(page, [(head, mark)], band.width, 1)
        cell, _rest = band.split_top(min(tall, band.height))
        page.boxes(cell, [(head, mark)])
