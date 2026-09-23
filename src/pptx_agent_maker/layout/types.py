"""The finite set of page shapes a deck may use.

**型を用意して「使ってください」にすると、使われない。**前の世代では版面の縦位置を
いくつか名前で持っていたが、頁は隣に自分の値を書き、名前のある位置のすぐ横に
名前のない値が積み上がった。読み手には、0.3mm のずれが重なった揺れとして届く。

ここでは頁が**型を選ぶことしかできない**。本文をどう割るかは型が持ち、宣言の側に
座標を書く口も、割り方を変える口も無い。型に収まらない頁は、型を足してから作る。

型は 12。既に組まれたデッキ群を数えて起こしてある ― よく使われた部品の組み合わせから
本文の型を 8 つ作り、実物を 1 冊ぶん通して収まらなかったものから骨格の型を 4 つ足した。
合成の見本では過不足が出ないので、**型の数は実物を通してからでないと決まらない**。

本文の型 ― どれも絵を必ず持つ:

    figure          絵 1 枚で本文を使い切る
    figure_note     絵 + その下に読み方
    figure_table    左に絵、右に表 (+ 読み方)
    figure_stack    絵の下に表 (+ 読み方)
    figures         絵を横に並べる (= 条件ちがいの比較)
    figure_grid     絵を格子に並べる (= 対象 × 条件のような 2 軸)
    cards_figure    上に並ぶカード、下に絵 (= 工程の説明)
    figure_points   左に絵、右に要点の並び

骨格の型 ― デッキの進行そのもので、絵を持たなくてよい:

    agenda          目次 (= 左に全項目、右にバケット。今いる章を強調する)
    flow            段が左から右へ流れる (= 各段にノード、段の下に条件。表を添えられる)
    board           表 1 枚が主役 (= 毎週積み上げる早見表)
    cards           カードの並びが主役 (= 今週の計画、まとめ。表を添えられる)

⚠ **絵を持たなくてよいのは骨格の 4 型だけ。**本文の型がここを外せるようになると、
「表と文章だけ」の頁が戻ってくる (= 実際にそれで作った頁は全部差し戻された)。

帯・読み方・出所はどの型でも任意で、書かなければその帯は取られない。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .geometry import Rect
from .page import Page, PageFullError
from .tokens import DEFAULT, Theme

#: A page type receives the frame it may divide and fills it.
Filler = Callable[[Page, "Spec"], None]

#: 全型が受け取れるキー (= 枠の宣言。書かなければその帯は取られない)
FRAME_KEYS = frozenset({"type", "kind", "title", "kicker", "condition", "conclusion",
                        "footer", "note", "replace"})

_TYPES: dict[str, tuple[Filler, frozenset, frozenset, bool]] = {}


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


def register(name: str, *, needs: Iterable[str], takes: Iterable[str] = (),
             figure: bool = True) -> Callable[[Filler], Filler]:
    """Declare a page type, what it must be given, and whether it must show a picture."""
    def decorate(filler: Filler) -> Filler:
        _TYPES[name] = (filler, frozenset(needs), frozenset(takes), figure)
        return filler
    return decorate


def skeleton() -> list[str]:
    """The types allowed to carry no figure (= the deck's own scaffolding)."""
    return sorted(name for name, spec in _TYPES.items() if not spec[3])


def names() -> list[str]:
    """Every type a page may ask for."""
    return sorted(_TYPES)


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
    filler(page, Spec(data, asset, aspect))
    return page


def _check_keys(name: str, data: dict, needs: frozenset, takes: frozenset) -> None:
    """Refuse a missing key and an unknown one alike.

    ⚠ **知らないキーを黙って捨てない。**綴り違いを捨てると、書いた人は書いたつもりで、
    焼いた頁にはそれが無い ― 前の世代で「design の値を変えても動かない」を 2 度踏んだ。
    """
    missing = sorted(needs - data.keys())
    if missing:
        raise PageTypeError(
            f"{name}: missing {', '.join(missing)} — this type is not that page without it"
        )
    unknown = sorted(data.keys() - needs - takes - FRAME_KEYS)
    if unknown:
        allowed = ', '.join(sorted(needs | takes | FRAME_KEYS))
        raise PageTypeError(
            f"{name}: does not take {', '.join(unknown)} (= it accepts {allowed}). "
            "A key nobody reads is a change that silently never happened."
        )


# -- the eight -------------------------------------------------------------


@register("figure", needs=["figure"], takes=["caption"])
def _figure(page: Page, spec: Spec) -> None:
    """One image using the whole body (= the page is the picture)."""
    source, aspect = spec.figure()
    page.figure(page.body, source, aspect, caption=spec.text("caption"))


@register("figure_note", needs=["figure", "note"], takes=["caption"])
def _figure_note(page: Page, spec: Spec) -> None:
    """An image with one or two lines telling the reader how to read it."""
    source, aspect = spec.figure()
    area, strip = page.body.rows([6, 1], gap=page.theme.spacing.gap_s)
    page.figure(area, source, aspect, caption=spec.text("caption"))
    page.note(strip, spec.text("note"))


@register("figure_table", needs=["figure", "table"], takes=["caption", "note", "weights"])
def _figure_table(page: Page, spec: Spec) -> None:
    """The picture on the left, the numbers on the right."""
    source, aspect = spec.figure()
    left, right = page.body.columns([3, 2], gap=page.theme.spacing.gap_m)
    page.figure(left, source, aspect, caption=spec.text("caption"))
    rows = spec.rows()
    placed, rest = right.split_top(page.theme.table_height(len(rows)),
                                   gap=page.theme.spacing.gap_s)
    page.table(placed, rows)
    if spec.text("note"):
        page.note(rest, spec.text("note"))


@register("figure_stack", needs=["figure", "table"], takes=["caption", "note"])
def _figure_stack(page: Page, spec: Spec) -> None:
    """The picture above, the numbers below (= wide figures, short tables)."""
    source, aspect = spec.figure()
    rows = spec.rows()
    needed = page.theme.table_height(len(rows))
    note = spec.text("note")
    reserve = needed + page.theme.spacing.gap_m
    area, rest = page.body.rows([page.body.height - reserve, reserve])
    page.figure(area, source, aspect, caption=spec.text("caption"))
    placed, after = rest.split_top(needed, gap=page.theme.spacing.gap_s)
    page.table(placed, rows)
    if note:
        page.note(after, note)


@register("figures", needs=["figures"], takes=["note"])
def _figures(page: Page, spec: Spec) -> None:
    """Images side by side — the shape for comparing conditions."""
    items = spec.figures()
    if len(items) < 2:
        raise PageTypeError("figures: put at least two images side by side, or use `figure`")
    area = page.body
    note = spec.text("note")
    if note:
        area, strip = page.body.rows([6, 1], gap=page.theme.spacing.gap_s)
    for cell, (source, aspect, caption) in zip(
            area.columns(len(items), gap=page.theme.spacing.gap_m), items):
        page.figure(cell, source, aspect, caption=caption)
    if note:
        page.note(strip, note)


@register("figure_grid", needs=["figures"], takes=["columns", "note"])
def _figure_grid(page: Page, spec: Spec) -> None:
    """Images on a grid — two axes at once (= item × method)."""
    items = spec.figures()
    columns = int(spec.get("columns", 3))
    if columns < 1:
        raise PageTypeError("figure_grid: `columns` must be at least 1")
    rows = -(-len(items) // columns)
    area = page.body
    note = spec.text("note")
    if note:
        area, strip = page.body.rows([8, 1], gap=page.theme.spacing.gap_s)
    cells = [cell for band in area.grid(rows, columns, gap=page.theme.spacing.gap_s)
             for cell in band]
    for cell, (source, aspect, caption) in zip(cells, items):
        page.figure(cell, source, aspect, caption=caption)
    if note:
        page.note(strip, note)


@register("cards_figure", needs=["cards", "figure"], takes=["caption", "note"])
def _cards_figure(page: Page, spec: Spec) -> None:
    """Cards across the top, the picture under them (= explaining a process)."""
    cards = [(str(head), str(body)) for head, body in spec.get("cards")]
    if not cards:
        raise PageTypeError("cards_figure: `cards` is empty")
    source, aspect = spec.figure()
    top, rest = page.body.rows([1, 2], gap=page.theme.spacing.gap_m)
    page.boxes(top, cards)
    note = spec.text("note")
    if note:
        rest, strip = rest.rows([5, 1], gap=page.theme.spacing.gap_s)
    page.figure(rest, source, aspect, caption=spec.text("caption"))
    if note:
        page.note(strip, note)


@register("figure_points", needs=["figure", "points"], takes=["caption"])
def _figure_points(page: Page, spec: Spec) -> None:
    """The picture on the left, what it shows on the right."""
    source, aspect = spec.figure()
    left, right = page.body.columns([3, 2], gap=page.theme.spacing.gap_m)
    page.figure(left, source, aspect, caption=spec.text("caption"))
    page.points(right, [str(item) for item in spec.get("points")])


def _card_height(page: Page, cards, width: int, columns: int, *, small: bool = False) -> int:
    """How tall the tallest card has to be for its own words.

    ⚠ **カードに頁の高さを配らない** ― 3 行のカードが 12cm の枠に入ると、字のうしろに
    その差ぶんの空きが残る (= 実際に焼いて出た)。
    """
    s, ty = page.theme.spacing, page.theme.type
    columns = max(columns, 1)
    # boxes が実際に割る幅と同じ出し方にする (= 列の間の空きを引いてから割る)
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


def _trailing(page: Page, spec: Spec, area):
    """Reserve the table and the note under a body, returning what is left for it.

    図解のとなりに数字を置く頁は実在する (= 「2 つの道」の絵と、その内訳の表)。
    表を別の型にすると同じ本体が 2 つの型に分かれるので、付属として持たせる。
    """
    note = spec.text("note")
    rows = spec.rows() if spec.get("table") is not None else None
    reserve = 0
    if rows is not None:
        widths = page.theme.column_widths(rows, area.width)
        reserve += page.theme.table_height(rows, widths) + page.theme.spacing.gap_m
    if note:
        reserve += page.theme.text_height(note, area.width) + page.theme.spacing.gap_s
    if not reserve:
        return area, None, ""
    body, _reserved = area.rows([max(area.height - reserve, 1), reserve])
    # 付属は「予約した帯」ではなく**本体が終わった所**から置く (= 本体が短く
    # 終わった頁で、読み方だけが頁の下端に取り残されるのを防ぐ)
    return body, (rows, area), note


def _place_trailing(page: Page, trailing, note: str, after: int | None = None) -> None:
    if trailing is None:
        return
    rows, rest = trailing
    if after is not None and after > rest.top:
        rest = Rect(rest.left, after + page.theme.spacing.gap_m, rest.width,
                    max(rest.bottom - after - page.theme.spacing.gap_m, 1))
    if rows is not None:
        placed = page.table(rest, rows)
        rest = Rect(rest.left, placed.bottom + page.theme.spacing.gap_s, rest.width,
                    max(rest.bottom - placed.bottom - page.theme.spacing.gap_s, 1))
    if note:
        page.note(rest, note)


# -- the scaffolding -------------------------------------------------------


@register("agenda", needs=["buckets"], takes=["highlight"], figure=False)
def _agenda(page: Page, spec: Spec) -> None:
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
    listing, right = page.body.columns([1, 1], gap=page.theme.spacing.gap_l)
    lines: list[str] = []
    for title, items in buckets:
        lines.append(title)
        lines.extend(f"    {item}" for item in items)
    page.points(listing, lines)
    # バケットは縦に積む (= 横に並べると、字のうしろに頁の高さぶんの空きが残る)
    for band, (number, (title, _items)) in zip(
            right.rows(len(buckets), gap=page.theme.spacing.gap_m),
            enumerate(buckets, start=1)):
        head = f"{number}. {title}"
        mark = "\u25c0 この章" if number == here else ""
        tall = _card_height(page, [(head, mark)], band.width, 1)
        cell, _rest = band.split_top(min(tall, band.height))
        page.boxes(cell, [(head, mark)])


@register("flow", needs=["stages"], takes=["note", "table"], figure=False)
def _flow(page: Page, spec: Spec) -> None:
    """Stages left to right, each holding its nodes, each with what is settled below.

    ⚠ **段の間の向きは文字で置く** (= `marker`)。矢印のプリセットを使わない。
    """
    stages = spec.get("stages")
    if len(stages) < 2:
        raise PageTypeError("flow: a flow needs at least two stages")
    area, trailing, note = _trailing(page, spec, page.body)

    # 段と段のあいだに、向きを置くための細い列を挟む
    weights: list[float] = []
    for index in range(len(stages)):
        if index:
            weights.append(0.18)
        weights.append(1.0)
    columns = area.columns(weights, gap=page.theme.spacing.gap_s)

    # ノードの高さは**そのノードの言葉**で決め、段ごとに積む。積んだ高さの最大に
    # 全段を揃えるので、列の下端は揃いながら、1 つしかない段が 2 つ分の空きを
    # 抱えることもない。等分で配っていた間は、3 行の本文が枠から溢れて下のノードに
    # 乗った (= 実際に焼いて 5 段とも溢れた)。
    gap = page.theme.spacing.gap_s
    stacks: list[list[tuple[tuple[str, str], int]]] = []
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
    stack = max(sum(h for _n, h in column) + gap * (len(column) - 1)
                for column in stacks)
    wanted = head_height + gap + stack + (gap + settled_height if settled_height else 0)
    if wanted > area.height:
        raise PageFullError(
            f"this flow needs {wanted} EMU of height and the body has {area.height} — "
            "shorten the nodes or split the stages across two pages; it will not shrink"
        )
    bottom = area.top + wanted

    for index, (stage, column_nodes) in enumerate(zip(stages, stacks)):
        column = columns[index * 2]
        if index:
            page.marker(columns[index * 2 - 1], "\u2192")
        head, rest = column.split_top(head_height, gap=gap)
        page.caption(head, str(stage["name"]))
        body, after = rest.split_top(stack, gap=gap)
        for node, height in column_nodes:
            cell, body = body.split_top(height, gap=gap)
            page.boxes(cell, [node], small=True)
        if stage.get("settled") and settled_height:
            page.caption(after.split_top(settled_height)[0], str(stage["settled"]),
                         align="left")
    _place_trailing(page, trailing, note, after=bottom)


@register("board", needs=["table"], takes=["note"], figure=False)
def _board(page: Page, spec: Spec) -> None:
    """One table using the page (= the figures are the numbers).

    ⚠ **これは例外の型。**「表と文章だけの頁を出さない」の唯一の抜け道で、毎週
    積み上げる早見表のためにある (= 頁の面積は数字に使い、説明は指標の頁が持つ)。
    本文の頁をここに逃がさない。
    """
    rows = spec.rows()
    placed = page.table(page.body, rows)
    if spec.text("note"):
        rest = Rect(page.body.left, placed.bottom + page.theme.spacing.gap_m,
                    page.body.width,
                    max(page.body.bottom - placed.bottom - page.theme.spacing.gap_m, 1))
        page.note(rest, spec.text("note"))


@register("cards", needs=["cards"], takes=["note", "columns", "table"], figure=False)
def _cards(page: Page, spec: Spec) -> None:
    """Cards filling the page (= this week's plan, what a chapter concluded)."""
    cards = [(str(head), str(body)) for head, body in spec.get("cards")]
    if not cards:
        raise PageTypeError("cards: `cards` is empty")
    columns = int(spec.get("columns", len(cards)))
    if columns < 1:
        raise PageTypeError("cards: `columns` must be at least 1")
    area, trailing, note = _trailing(page, spec, page.body)
    lines = -(-len(cards) // columns)
    tall = _card_height(page, cards, area.width, columns)
    used = min(tall * lines + page.theme.spacing.gap_m * (lines - 1), area.height)
    area, _spare = area.split_top(used)
    for index, band in enumerate(area.rows(lines, gap=page.theme.spacing.gap_m)):
        page.boxes(band, cards[index * columns:(index + 1) * columns])
    _place_trailing(page, trailing, note, after=area.bottom)
