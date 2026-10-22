"""The types allowed to carry no picture: the deck's own scaffolding."""

from __future__ import annotations

from ...base.geometry import Rect
from ...parts.elements import Ellipse, Fill, Text
from ...parts.look import Style
from ...parts.page import Card, Page, PageFullError
from ..core.read import Spec, read_tone
from ..core.registry import PageTypeError, register
from ..core.stack import card_height


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


#: 章の番号の出し方 (= `numbers`)。丸の数字は字として在るのが 20 まで
NUMBERS = ("plain", "circled")
_CIRCLED = 0x2460


def _numbered(spec: Spec, count: int):
    """How a chapter's number is written in front of its name (= `1.` unless the page asks for circles)."""
    numbers = spec.get("numbers", "plain")
    if not isinstance(numbers, str) or numbers not in NUMBERS:
        raise PageTypeError(
            f"agenda: `numbers` is {numbers!r} — chapters are numbered {' or '.join(repr(n) for n in NUMBERS)}")
    if numbers == "circled" and count > 20:
        raise PageTypeError(
            f"agenda: {count} chapters cannot be numbered in circles — the circled numbers stop at 20")
    return (lambda number: chr(_CIRCLED + number - 1)) if numbers == "circled" else (lambda number: f"{number}.")


#: 目次の描き方 (= `look`)。`boxes` は字の高さの箱、`cards` は右の列を章の数で等分した角丸のカードに、
#: 番号を塗りの丸で置く (= 案件の資料で使ってきた目次の形)
LOOKS = ("boxes", "cards")
#: `cards` の右の列の見出し
CARDS_HEADING = "アジェンダ"
#: 章の名前と要旨を分ける記号 (= `名前 ― 要旨` は、名前を太字の 1 行目、要旨を細字の 2 行目にする)
SUMMARY = " ― "


#: `cards` の左の列と右の列の幅の比 (= 案件の資料の目次は、 一覧の側が少し広い)
CARDS_COLUMNS = (11, 10)
#: 左の一覧の章の印 (= 章の字と同じ色) と小項目の印 (= 字は本文の色、 印だけ灰)。 どちらも字とは別の箱に置く
#: (= 印を字と同じ run に入れると、 頁を複製して章の名前を差し替える時に、 印付きの文言を別に書くことになる)
CHAPTER_MARK, ITEM_MARK = "\u2022", "\u2013"
#: 左の一覧の印の出し方 (= `list_marks`)。`marks` は上の 2 つの印、`numbers` は章を「1」、小項目を章ごとに「(1)」と
#: 番号で置き、下の段には印を置かない (= 下の段は頁の名前で、頁の名前が自分の番号を持つ)
LIST_MARKS = ("marks", "numbers")


#: 章の中身 1 つ (= 小項目の名前と、 その下に並べる名前。 下の段を書かない小項目は空の並び)
Item = tuple[str, list[str]]
#: 章 1 つ (= 章の名前と、 その小項目)
Chapter = tuple[str, list[Item]]


def _read_buckets(raw: list, here: int) -> list[Chapter]:
    """The chapters `buckets` writes, each item with the names under it, folded to the chapter in hand.

    小項目は名前か `["名前", ["下の段", …]]` (= 章 → 小項目 → 下の段の 3 段)。 下の段を出すのは `highlight` の
    章だけで、 章を名指さない目次は全部の章で出す (= 進行型の目次では、 ほかの章は小項目までで章の形が読める。
    全部の章の下の段を並べると、 一覧が頁に入らない)。
    """
    chapters: list[Chapter] = []
    for number, (title, items) in enumerate(raw, start=1):
        read: list[Item] = []
        for item in items:
            if not isinstance(item, (list, tuple)):
                read.append((str(item), []))
                continue
            if (len(item) != 2 or isinstance(item[0], (list, tuple)) or not isinstance(item[1], (list, tuple))
                    or any(isinstance(name, (list, tuple)) for name in item[1])):
                raise PageTypeError(
                    f"agenda: an item of chapter {number} is {item!r} — an item is a name, or "
                    "[name, [the names under it]], and the names under it hold nothing under them")
            read.append((str(item[0]), [str(name) for name in item[1]] if not here or number == here else []))
        chapters.append((str(title), read))
    return chapters


def _agenda_cards(page: Page, area: Rect, buckets: list[Chapter], here: int, item: int, numbered: bool) -> None:
    """The agenda drawn as cards: the list on the left, a heading and one card per chapter on the right.

    左の一覧は章を `•` で章の大きさの字に、 小項目を一段下げた `–` で本文の字に、 小項目の下の段をもう一段
    下げた `–` で本文の字にし、 今の章だけ差し色の太字にする (= `highlight_item` は今の章の小項目を 1 つ差し色の
    太字にする。 章の途中から入り直す頁のため)。 ほかは本文の色で、 小項目と下の段の印だけ灰。 右のカードは列の
    高さを章の数で等分し、 番号は塗りの丸に置く。 今の章は差し色の丸に紙の色の数字、 差し色のごく薄い地、 差し色の題。 ほかの章は灰の丸に本文の色の数字、 灰の地、
    灰の題 (= 灰の丸の上の白や灰の数字は読めない)。 枠は引かない。
    `numbered` (= `list_marks = "numbers"`) は左の一覧の印を番号にする (= 章は右のカードの丸と同じ数、 小項目は章ごとに
    「(1)」 から、 下の段は印なし)。 印の幅は段ごとに一番広い物に揃え、 同じ段の字の頭を揃える。
    """
    theme = page.theme
    t, s, p = theme.type, theme.spacing, theme.palette
    listing, right = area.columns(list(CARDS_COLUMNS), gap=s.gap_l)
    # 印の箱は余白なしで、 印と空白 1 つ分の幅 (= 字の箱の左の余白が印と字の間になる。 余白のある箱を印と空白
    # の幅にすると、 LibreOffice は印を次の行へ折って隠す)
    indent = s.gap_l + s.gap_m
    # (印, 印の色, 字, 字の大きさ, 字の色, 太字, 字下げ, 前の間)。 章の印は章の字と同じ色、 小項目の印は灰
    rows: list[tuple[str, str, str, int, str, bool, int, int]] = []
    for number, (title, items) in enumerate(buckets, start=1):
        marked = number == here
        colour = p.accent if marked else p.ink
        rows.append((str(number) if numbered else CHAPTER_MARK, colour, title.split(SUMMARY, 1)[0], t.stage, colour,
                     marked, 0, s.gap_s if rows else 0))
        for index, (entry, under) in enumerate(items, start=1):
            picked = marked and index == item
            rows.append((f"({index})" if numbered else ITEM_MARK, p.accent if picked else p.muted, entry, t.body,
                         p.accent if picked else p.ink, picked, indent, s.row_gap))
            rows.extend(("" if numbered else ITEM_MARK, p.muted, name, t.body, p.ink, False, 2 * indent, s.row_gap)
                        for name in under)
    # 印の幅は段 (= 字下げ) ごとに一番広い物 (= 「(9)」 と 「(10)」 の後の字の頭が揃う)。 印の無い段は幅を取らない
    widest: dict[int, int] = {}
    for sign, _shade, _text, size, _colour, _bold, indent, _before in rows:
        if sign:
            widest[indent] = max(widest.get(indent, 0), theme.width(f"{sign} ", size))
    marks = [widest.get(indent, 0) for *_head, indent, _before in rows]
    heights = [theme.wrapped_height(text, max(listing.width - indent - mark - 3 * s.text_inset, 1), size, bold=bold)
               for (_sign, _shade, text, size, _colour, bold, indent, _before), mark in zip(rows, marks)]
    if sum(heights) + sum(row[-1] for row in rows) > listing.height:
        raise PageFullError(
            f"agenda: the list of items needs {sum(heights) + sum(row[-1] for row in rows)} EMU of height and has "
            f"{listing.height} — fewer items, or two pages; it will not shrink")
    top = listing.top
    for (sign, shade, text, size, colour, bold, indent, before), mark, tall in zip(rows, marks, heights):
        top += before
        # 印は、 字の箱の左の余白と同じだけ一覧の端から下げる (= 印の箱は余白なし。 揃えないと印が列の外へ出る)
        left = listing.left + indent + s.text_inset
        if sign:
            page.elements.append(Text("agenda_mark", Rect(left, top, mark, theme.line_height(size)), sign, size, shade))
        left += mark
        page.elements.append(Text("agenda_item", Rect(left, top, listing.right - left, tall), text, size, colour,
                                  bold=bold))
        top += tall
    head, stack = right.split_top(theme.line_height(t.stage), gap=s.gap_m)
    page.elements.append(Text("agenda_heading", head, CARDS_HEADING, t.stage, p.ink, bold=True))
    # 番号の丸は見出しの行 2 つ分 (= 案件の資料の丸の大きさ)
    disc = 2 * theme.line_height(t.heading)
    for band, (number, (title, _items)) in zip(stack.rows(len(buckets), gap=s.gap_s),
                                                enumerate(buckets, start=1)):
        marked = number == here
        colour = p.accent if marked else p.muted
        name, _, summary = title.partition(SUMMARY)
        circle = Rect(band.left + s.gap_m, band.top + (band.height - disc) // 2, disc, disc)
        words = Rect(circle.right + s.gap_m, band.top + s.pad,
                     max(band.right - s.pad - circle.right - s.gap_m, 1), max(band.height - 2 * s.pad, 1))
        width = max(words.width - 2 * s.text_inset, 1)
        named = theme.wrapped_height(name, width, t.stage, bold=True)
        said = theme.wrapped_height(summary, width, t.body) if summary else 0
        if max(named + said, disc) > band.height - 2 * s.pad:
            raise PageFullError(
                f"agenda: chapter {number} needs {max(named + said, disc) + 2 * s.pad} EMU of height and its "
                f"share of the page is {band.height} — fewer chapters, or shorter names; it will not shrink")
        page.elements.append(Fill("agenda_card", band, p.thinned(p.FAINT) if marked else p.wash, rounded=True))
        page.elements.append(Ellipse("agenda_disc", circle, p.accent if marked else p.rule))
        # ほかの章の番号は本文の色 (= 灰の丸の上の灰の字は、テンプレートによって読めない。 案件のテンプレートで
        # 丸 E7E6E6 に字 8B8B8B が比 2.7 になり、 contrast の検査が赤にした)
        page.elements.append(Text("agenda_number", circle, str(number), t.heading,
                                  p.paper if marked else p.ink, bold=True, align="center"))
        top = words.top + (words.height - named - said) // 2
        page.elements.append(Text("agenda_chapter", Rect(words.left, top, words.width, named), name, t.stage,
                                  colour, bold=True))
        if summary:
            page.elements.append(Text("agenda_summary", Rect(words.left, top + named, words.width, said),
                                      summary, t.body, colour))


@register("agenda", needs=["buckets"],
          takes=["highlight", "highlight_tone", "numbers", "look", "highlight_item", "list_marks"], figure=False)
def _agenda(page: Page, spec: Spec, area: Rect) -> None:
    """Every item on the left, the buckets on the right, this chapter marked.

    進行型の目次 (= 章の頭ごとに 1 枚置き、その章だけを強調する)。⚠ **実頁の無い
    小項目を書かない** ― 目次に残すと翌週がそれを輸入して持ち越す。

    小項目は `["名前", ["下の段", …]]` と書けば、その下にもう 1 段並ぶ (= 章 → 中の段 → 頁の名前)。下の段が
    出るのは `highlight` の章だけ (= 章を名指さない目次は全部の章)。

    強調は、書かなければ章の名前の下の言葉 (= `◀ この章`)。`highlight_tone` を書けば、その章の箱が
    その地になり、言葉は置かない (= 地が言っていることを、もう 1 度言葉で言わない)。`numbers = "circled"`
    は章の番号を丸の数字で書く。`look = "cards"` の `list_marks = "numbers"` は、左の一覧の印を番号にする。

    ⚠ **一覧も章の箱も、自分の言葉ぶんの高さが取れなければ止まる。**取れる高さに切り詰めて置いて
    いた間は、箱の中の字が箱の下の線に乗った (= 狭いマスに入れた目次で、焼いて出た)。
    """
    raw = spec.get("buckets")
    if not raw:
        raise PageTypeError("agenda: `buckets` is empty — an agenda with no chapters")
    here = int(spec.get("highlight", 0))
    if here and not 1 <= here <= len(raw):
        raise PageTypeError(
            f"agenda: `highlight` is {here}, but there are {len(raw)} buckets"
        )
    buckets = _read_buckets(raw, here)
    look = spec.get("look", "boxes")
    if not isinstance(look, str) or look not in LOOKS:
        raise PageTypeError(f"agenda: `look` is {look!r} — an agenda is drawn as {' or '.join(map(repr, LOOKS))}")
    item = spec.get("highlight_item")
    if item is not None:
        if look != "cards":
            raise PageTypeError("agenda: `highlight_item` marks an item of the list `look = \"cards\"` draws")
        if (not here or isinstance(item, bool) or not isinstance(item, int)
                or not 1 <= item <= len(buckets[here - 1][1])):
            raise PageTypeError(
                f"agenda: `highlight_item` is {item!r} — the number of an item of the chapter `highlight` names")
    marks = spec.get("list_marks")
    if marks is not None:
        if look != "cards":
            raise PageTypeError("agenda: `list_marks` sets the marks of the list `look = \"cards\"` draws")
        if not isinstance(marks, str) or marks not in LIST_MARKS:
            raise PageTypeError(
                f"agenda: `list_marks` is {marks!r} — the list is marked {' or '.join(map(repr, LIST_MARKS))}")
    if look == "cards":
        for taken in ("highlight_tone", "numbers"):
            if spec.get(taken) is not None:
                raise PageTypeError(
                    f"agenda: `{taken}` is for the boxes; the cards number their chapters in discs and "
                    "mark this one in the accent")
        _agenda_cards(page, area, buckets, here, item or 0, marks == "numbers")
        return
    ground = spec.get("highlight_tone")
    if ground is not None:
        if not here:
            raise PageTypeError(
                "agenda: `highlight_tone` is the ground of the chapter `highlight` names, and no chapter is named")
        ground = read_tone(spec, {"tone": ground}, "agenda: `highlight_tone`", "box")
    number_of = _numbered(spec, len(buckets))
    listing, right = area.columns([1, 1], gap=page.theme.spacing.gap_l)
    lines: list[str] = []
    for title, items in buckets:
        lines.append(title)
        for entry, under in items:
            lines.append(f"    {entry}")
            lines.extend(f"        {name}" for name in under)
    listed = page.points_height(listing.width, lines)
    if listed > listing.height:
        raise PageFullError(
            f"agenda: the list of items needs {listed} EMU of height and has {listing.height} — "
            "fewer items, or two pages; it will not shrink")
    page.points(listing, lines)
    for band, (number, (title, _items)) in zip(
            right.rows(len(buckets), gap=page.theme.spacing.gap_m),
            enumerate(buckets, start=1)):
        head = f"{number_of(number)} {title}"
        marked = number == here
        card = Card(head, "◀ この章" if marked and ground is None else "",
                    Style(ground) if marked and ground is not None else Style())
        tall = card_height(page, [card], band.width, 1)
        if tall > band.height:
            raise PageFullError(
                f"agenda: chapter {number} needs {tall} EMU of height and its share of the page is "
                f"{band.height} — fewer chapters, or shorter names; it will not shrink")
        # 頁の高さを使う資料 (= `box_height = "page"`) では、章の箱は列の等分を使い切る
        cell = band if page.theme.box_height == "page" else band.split_top(tall)[0]
        page.boxes(cell, [card])
