"""Ways to arrange boxes that rows and cells cannot: a ring, a tree, circles that overlap.

`compose` のマスに置く部品のうち、**箱どうしの並びそのものが意味を持つ物**。どれも渡された枠を割るだけで、
座標は書かない (= 箱の数と中身から位置が決まる)。字の大きさと色は箱 (= カード) と同じ表から来る。

* **輪 (`ring`)** ― 回り続ける段 (= 計画・実行・評価・改善)。箱を枠いっぱいの楕円の上に、上から時計回りに
  置き、隣どうしを矢印でつなぐ (= 最後の箱から最初の箱へも)
* **木 (`tree`)** ― 親と子 (= 組織、分類、課題の分解)。上から下へ段に分け、子は親の下に並び、親から子へ
  線を引く。葉の数で幅を割る
* **重なり (`overlap`)** ― 2 つか 3 つの集まりと、その共通部分 (= ベン図)。円を透かして重ね、重なった所に
  共通の言葉を置く
* **絵の上の印 (`marks`)** ― 写真や図の 1 点を指して名前を付ける (= 製品の各部、画面の各所)。点の位置だけは
  絵に対する割合で書く (= 頁の座標ではないので、絵の外へは出ない)。名前は絵の左右の列に並び、点まで線が引かれる
* **マスどうしの線 (`links`)** ― `compose` の頁で、`id` を付けたマスからマスへ矢印を引く (= 隣り合うマスだけ)。
  入れ物 (`panel`) の中のマスと外のマスも結べ、入れ物そのものも端になる (= 入れ物とその中身は結べない)。
  色の役 (`tone`) と、矢印のそばに置く言葉 (`text`) も書ける

⚠ **収まらなければ縮めずに止まる** (= どの並べ方も、箱か字を小さくして押し込むことはしない)。
"""

from __future__ import annotations

import math

from ...base.geometry import Rect, pt
from ...parts.page import Card, Page, PageFullError
from ..core.read import Spec, read_card, read_tone, only_keys
from ..core.registry import PageTypeError
from ..core.stack import card_height

#: 輪に置ける箱の数 (= 2 つは往復で、輪ではない。9 つからは箱が読める大きさで回らない)
RING = (3, 8)
#: 木の段の数の上限 (= 根を含む。5 段からは 1 頁の高さで箱が読める大きさに並ばない)
DEPTH = 4
#: 重なりの円が隣の円と重なる幅 (= 直径に対する比)。ベン図の通り名の形 (= 共通部分に言葉が入り、
#: それぞれだけの所も残る)
LENS = 0.4
#: 重なった円の透け方 (= 重なった所が濃く見える)
CLEAR = 0.35
#: 印の名の列が取ってよい幅の上限 (= マスの幅に対する比。左右に列が立っても、絵がマスの 3 分の 1 は残る)
MARK_COLUMN = 1 / 3
#: 木の箱の子を持つ側のキー
TREE_KEYS = ("heading", "body", "tone", "icon", "tentative", "strong", "children")
#: マスどうしの線 1 本が読むキー
LINK_KEYS = ("from", "to", "text", "tone")


# -- 輪 ----------------------------------------------------------------------


def ring_cards(spec: Spec, items, what: str) -> list[Card]:
    if not isinstance(items, list) or not RING[0] <= len(items) <= RING[1]:
        raise PageTypeError(f"{what}: `ring` is a list of {RING[0]} to {RING[1]} boxes, written like cards")
    return [read_card(spec, item, f"{what}, box {number}") for number, item in enumerate(items, start=1)]


def _centres(rect: Rect, count: int, width: int, height: int) -> list[tuple[int, int]]:
    """Where each box's middle goes: on the ellipse the boxes just fit in, from the top, clockwise."""
    cx, cy = rect.left + rect.width // 2, rect.top + rect.height // 2
    rx, ry = (rect.width - width) / 2, (rect.height - height) / 2
    return [(round(cx + rx * math.sin(2 * math.pi * i / count)), round(cy - ry * math.cos(2 * math.pi * i / count)))
            for i in range(count)]


def _apart(boxes: list[Rect], gap: int) -> bool:
    return not any(a.left < b.right + gap and b.left < a.right + gap and a.top < b.bottom + gap and b.top < a.bottom + gap
                   for i, a in enumerate(boxes) for b in boxes[i + 1:])


def ring(page: Page, rect: Rect, cards: list[Card], what: str) -> None:
    """Boxes round an ellipse, as wide as they can be without touching, joined by arrows in turn."""
    s = page.theme.spacing
    step = max(s.gap_s // 3, 1)
    floor = max(page.theme.unbreakable(card.heading, page.theme.type.heading, bold=True) for card in cards) \
        + 2 * (s.pad + s.text_inset)
    width = rect.width // 2
    while width >= floor:
        height = card_height(page, cards, width, 1)
        if height <= rect.height // 2:
            boxes = [Rect(x - width // 2, y - height // 2, width, height)
                     for x, y in _centres(rect, len(cards), width, height)]
            if _apart(boxes, s.gap_l):
                break
        width -= step
    else:
        raise PageFullError(
            f"{what}: {len(cards)} boxes do not go round this cell without touching — give the cell more room, "
            "shorten the words, or use fewer boxes; nothing will shrink")
    for box, card in zip(boxes, cards):
        page.boxes(box, [card])
    for number, box in enumerate(boxes):
        after = boxes[(number + 1) % len(boxes)]
        start, end = _between(box, after, s.gap_s)
        page.line(start, end, arrow=True)
    page.drew_a_diagram()


def _between(a: Rect, b: Rect, gap: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """The stretch of the line from a's middle to b's middle that lies outside both boxes, `gap` off each."""
    (ax, ay), (bx, by) = _middle(a), _middle(b)
    dx, dy = bx - ax, by - ay
    leave, enter = _exit(a, dx, dy), 1 - _exit(b, -dx, -dy)
    length = math.hypot(dx, dy) or 1
    leave += gap / length
    enter -= gap / length
    return (round(ax + dx * leave), round(ay + dy * leave)), (round(ax + dx * enter), round(ay + dy * enter))


def _middle(rect: Rect) -> tuple[int, int]:
    return rect.left + rect.width // 2, rect.top + rect.height // 2


def _exit(rect: Rect, dx: float, dy: float) -> float:
    """How far along (dx, dy) from the box's middle the line leaves the box (= 0 to 1 of the whole)."""
    half_w, half_h = rect.width / 2, rect.height / 2
    reach = [half_w / abs(dx) if dx else math.inf, half_h / abs(dy) if dy else math.inf]
    return min(reach)


# -- 木 ----------------------------------------------------------------------


class _Node:
    def __init__(self, card: Card, children: list["_Node"]):
        self.card, self.children = card, children

    def leaves(self) -> int:
        return sum(child.leaves() for child in self.children) or 1

    def levels(self) -> int:
        return 1 + max((child.levels() for child in self.children), default=0)


def tree_root(spec: Spec, item, what: str, depth: int = 1) -> _Node:
    if not isinstance(item, dict):
        raise PageTypeError(f"{what}: a box of a tree is {{ heading = …, body = …, children = [ … ] }}")
    only_keys(item, set(TREE_KEYS), what)
    children = item.get("children", [])
    if not isinstance(children, list):
        raise PageTypeError(f"{what}: `children` is a list of boxes")
    if children and depth >= DEPTH:
        raise PageTypeError(f"{what}: a tree goes {DEPTH} levels deep at most (= the root is the first)")
    card = read_card(spec, {k: v for k, v in item.items() if k != "children"}, what)
    return _Node(card, [tree_root(spec, child, f"{what}, child {number}", depth + 1)
                        for number, child in enumerate(children, start=1)])


def _tree_plan(page: Page, root: _Node, width: int) -> tuple[int, list[int]]:
    """The width of one box and the height of each level."""
    s = page.theme.spacing
    leaves = root.leaves()
    box = (width - s.gap_m * (leaves - 1)) // leaves
    levels: list[list[Card]] = []

    def walk(node: _Node, depth: int) -> None:
        if len(levels) <= depth:
            levels.append([])
        levels[depth].append(node.card)
        for child in node.children:
            walk(child, depth + 1)

    walk(root, 0)
    floor = max(page.theme.unbreakable(card.heading, page.theme.type.heading, bold=True)
                for cards in levels for card in cards) + 2 * (s.pad + s.text_inset)
    if box < floor:
        raise PageFullError(f"{leaves} boxes side by side leave each {box} EMU, narrower than the longest word "
                            "of a heading — fewer leaves, shorter headings, or two pages; nothing will shrink")
    return box, [card_height(page, cards, box, 1) for cards in levels]


def tree_height(page: Page, root: _Node, width: int) -> int:
    _box, heights = _tree_plan(page, root, width)
    return sum(heights) + page.theme.spacing.gap_l * (len(heights) - 1)


def tree(page: Page, rect: Rect, root: _Node, what: str) -> None:
    """Levels top to bottom; each box over the leaves it holds; a line down from parent to children."""
    s = page.theme.spacing
    box, heights = _tree_plan(page, root, rect.width)
    tops = [rect.top]
    for height in heights[:-1]:
        tops.append(tops[-1] + height + s.gap_l)

    def place(node: _Node, depth: int, first_leaf: int) -> Rect:
        span = node.leaves()
        left = rect.left + first_leaf * (box + s.gap_m)
        right = rect.left + (first_leaf + span) * (box + s.gap_m) - s.gap_m
        here = Rect(left + (right - left - box) // 2, tops[depth], box, heights[depth])
        page.boxes(here, [node.card])
        if node.children:
            leaf = first_leaf
            bottoms = []
            for child in node.children:
                bottoms.append(place(child, depth + 1, leaf))
                leaf += child.leaves()
            x = here.left + here.width // 2
            bus = here.bottom + s.gap_l // 2
            page.line((x, here.bottom), (x, bus))
            centres = [child.left + child.width // 2 for child in bottoms]
            if len(centres) > 1:
                page.line((min(centres), bus), (max(centres), bus))
            for centre, child in zip(centres, bottoms):
                page.line((centre, bus), (centre, child.top))
        return here

    place(root, 0, 0)
    page.drew_a_diagram()


# -- 重なり ------------------------------------------------------------------


def overlap_sets(spec: Spec, data, what: str) -> tuple[list[tuple[str, str]], str]:
    """The sets (= each its name and its tone) and the words for what they share."""
    if not isinstance(data, dict):
        raise PageTypeError(f"{what}: `overlap` is {{ sets = [ … ], shared = \"…\" }}")
    only_keys(data, {"sets", "shared"}, what)
    sets = data.get("sets")
    if not isinstance(sets, list) or len(sets) not in (2, 3):
        raise PageTypeError(f"{what}: `sets` is 2 or 3 sets, each \"name\" or {{ name = …, tone = … }}")
    found = []
    for number, item in enumerate(sets, start=1):
        where = f"{what}: set {number}"
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict) or not str(item.get("name", "")).strip():
            raise PageTypeError(f"{where} has no name")
        only_keys(item, {"name", "tone"}, where)
        default = ("box", "band", "tint")[number - 1]
        found.append((str(item["name"]).strip(), read_tone(spec, item, where, default) if "tone" in item else default))
    return found, str(data.get("shared", "")).strip()


def overlap(page: Page, rect: Rect, sets: list[tuple[str, str]], shared: str, what: str) -> None:
    """Two circles side by side, or three in a triangle, let through where they cross; names in their own parts."""
    s, ty = page.theme.spacing, page.theme.type
    step = 1 - LENS
    if len(sets) == 2:
        size = min(rect.width / (1 + step), rect.height)
        spread = [(0.0, 0.0), (step, 0.0)]
        wide, tall = (1 + step) * size, size
    else:
        size = min(rect.width / (1 + step), rect.height / (1 + step * math.sin(math.pi / 3)))
        spread = [(0.0, 0.0), (step, 0.0), (step / 2, step * math.sin(math.pi / 3))]
        wide, tall = (1 + step) * size, (1 + step * math.sin(math.pi / 3)) * size
    diameter = round(size)
    left, top = rect.left + round((rect.width - wide) / 2), rect.top + round((rect.height - tall) / 2)
    circles = [Rect(left + round(x * size), top + round(y * size), diameter, diameter) for x, y in spread]
    for circle, (_name, tone) in zip(circles, sets):
        page.circle(circle, tone, clear=CLEAR)
    # それぞれだけの所: 円の中で、ほかの円から遠い側の 3 分の 1 (= 円の外へ向かう側)
    middle = (sum(c.left + c.width / 2 for c in circles) / len(circles),
              sum(c.top + c.height / 2 for c in circles) / len(circles))
    # 名前の枠は 1 辺が重なりの幅の正方形。それぞれだけの所の真ん中は、円の真ん中から外へ重なりの幅の半分
    # (= 2 つの円なら、自分の縁から隣の円の縁までの真ん中)
    room = round(diameter * LENS)
    for circle, (name, _tone) in zip(circles, sets):
        cx, cy = circle.left + circle.width / 2, circle.top + circle.height / 2
        dx, dy = cx - middle[0], cy - middle[1]
        reach = math.hypot(dx, dy) or 1
        away = diameter * LENS / 2
        x, y = cx + dx / reach * away, cy + dy / reach * away
        _words(page, Rect(round(x - room / 2), round(y - room / 2), room, room), name, ty.heading, True, what)
    if shared:
        _words(page, Rect(round(middle[0] - room / 2), round(middle[1] - room / 2), room, room), shared,
               ty.body, False, what)
    page.drew_a_diagram()


def _words(page: Page, rect: Rect, text: str, size: float, bold: bool, what: str) -> None:
    s = page.theme.spacing
    needed = page.theme.wrapped_height(text, max(rect.width - 2 * s.text_inset, 1), size, bold=bold)
    if needed > rect.height:
        raise PageFullError(f"{what}: {text[:20]!r} does not fit its part of the circles — shorter words, "
                            "or give the cell more room; nothing will shrink")
    page.words(Rect(rect.left, rect.top + (rect.height - needed) // 2, rect.width, needed), text, size, bold=bold)


# -- 絵の上の印 --------------------------------------------------------------


def read_marks(items, what: str) -> list[tuple[float, float, str]]:
    """Each mark: where on the picture (= across and down, 0 to 1) and what it is called."""
    if not isinstance(items, list) or not items:
        raise PageTypeError(f"{what}: `marks` is a list of {{ at = [across, down], text = \"…\" }}, at least one")
    found = []
    for number, item in enumerate(items, start=1):
        where = f"{what}: mark {number}"
        only_keys(item, {"at", "text"}, where)
        at, text = item.get("at"), str(item.get("text", "")).strip()
        if (not isinstance(at, list) or len(at) != 2 or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                                                 and 0 <= v <= 1 for v in at)):
            raise PageTypeError(f"{where}: `at` is [across, down] on the picture, each from 0 (= left, top) to 1")
        if not text:
            raise PageTypeError(f"{where} has no `text` — a mark is there to name what it points at")
        found.append((float(at[0]), float(at[1]), text))
    return found


def marked_figure(page: Page, rect: Rect, source, aspect: float, marks: list[tuple[float, float, str]],
                  caption: str, what: str) -> None:
    """The picture between two columns of names, a thin line from each name to the point it names.

    名前は、点が絵の左半分なら左の列、右半分なら右の列に、点の高さに合わせて並ぶ (= 重なれば下へずらし、
    下に余らなければ上へ戻す)。列の幅はいちばん長い名前の 1 行ぶん (= マスの 3 分の 1 まで)。
    """
    s, ty = page.theme.spacing, page.theme.type
    sides = {"left": [m for m in marks if m[0] < 0.5], "right": [m for m in marks if m[0] >= 0.5]}
    widths = {side: min(max(page.theme.width(text, ty.body) for _x, _y, text in group) + 2 * s.text_inset,
                        int(rect.width * MARK_COLUMN)) if group else 0 for side, group in sides.items()}
    left = rect.left + (widths["left"] + s.gap_l if widths["left"] else 0)
    right = rect.right - (widths["right"] + s.gap_l if widths["right"] else 0)
    # 絵は上に寄る (= 印の無い絵と同じ。同じ段の物と上端が揃う)。取る高さは絵の幅で決まる高さと名の行だけ
    named = s.gap_s + page.theme.wrapped_height(caption, max(right - left - 2 * s.text_inset, 1), ty.caption) \
        if caption else 0
    tall = min(round((right - left) / aspect) + named, rect.height)
    placed = page.figure(Rect(left, rect.top, right - left, tall), source, aspect, caption=caption)
    for side, group in sides.items():
        if not group:
            continue
        width = widths[side]
        column = rect.left if side == "left" else rect.right - width
        heights = [page.theme.wrapped_height(text, max(width - 2 * s.text_inset, 1), ty.body) for _x, _y, text in group]
        order = sorted(range(len(group)), key=lambda i: group[i][1])
        tops = {}
        below = rect.top
        for i in order:
            point = placed.top + group[i][1] * placed.height
            tops[i] = max(round(point - heights[i] / 2), below)
            below = tops[i] + heights[i] + s.gap_s
        above = rect.bottom
        for i in reversed(order):
            tops[i] = min(tops[i], above - heights[i])
            above = tops[i] - s.gap_s
        if tops[order[0]] < rect.top:
            raise PageFullError(f"{what}: the names on the {side} of the picture need more height than the cell has "
                                "— fewer marks, shorter names, or a taller row; nothing will shrink")
        dot = s.mark // 2
        for i, (x, y, text) in enumerate(group):
            label = Rect(column, tops[i], width, heights[i])
            page.words(label, text, ty.body, align="right" if side == "left" else "left")
            point = (round(placed.left + x * placed.width), round(placed.top + y * placed.height))
            edge = label.right if side == "left" else label.left
            page.line((edge + (s.gap_s if side == "left" else -s.gap_s), label.top + label.height // 2), point)
            page.circle(Rect(point[0] - dot // 2, point[1] - dot // 2, dot, dot), "accent")


# -- マスどうしの線 ----------------------------------------------------------


def links(page: Page, spec: Spec, written, cells: dict[str, Rect], every: list[Rect], blank: list[Rect],
          what: str) -> None:
    """An arrow from each cell named in `from` to the one in `to`, across the gap where the two face each other.

    `every` は頁の全部のマス (= `id` の無いマスも)。2 つのあいだに別のマスが在れば、線はそれを横切るので止める。
    ただし `blank` (= 中身の無いマス。`text = ""`) は空きなので数えない (= 離れた 2 つのマスを、間の空きを
    またいで結べる)。`tone` は矢印の色の役 (= 書かなければ灰)、`text` は矢印のそばの言葉 (= `_words_by`)。
    """
    if not isinstance(written, list) or not written:
        raise PageTypeError(f"{what}: `links` is a list of {{ from = \"id\", to = \"id\" }}")
    for number, item in enumerate(written, start=1):
        where = f"{what}: link {number}"
        only_keys(item, set(LINK_KEYS), where)
        ends = [str(item.get(key, "")) for key in ("from", "to")]
        missing = [end for end in ends if end not in cells]
        if missing:
            known = ", ".join(sorted(cells)) or "none — give the cells an `id`"
            raise PageTypeError(f"{where}: no cell has the id {missing[0]!r} (= the ids on this page: {known})")
        tone = read_tone(spec, item, where, "box") if "tone" in item else None
        words = item.get("text")
        if "text" in item and (not isinstance(words, str) or not words.strip()):
            raise PageTypeError(f"{where}: `text` is the words set beside the arrow, not {words!r} — "
                                "drop the key for an arrow without words")
        a, b = cells[ends[0]], cells[ends[1]]
        if a.contains(b) or b.contains(a):
            holder, held = (ends[0], ends[1]) if a.contains(b) else (ends[1], ends[0])
            raise PageTypeError(f"{where}: {holder!r} holds {held!r} — a link joins two cells side by side or one "
                                "above the other, not a cell and what stands inside it")
        if a.top < b.bottom and b.top < a.bottom:                       # 横に向き合う
            y = (max(a.top, b.top) + min(a.bottom, b.bottom)) // 2
            start, end = ((a.right, y), (b.left, y)) if a.right <= b.left else ((a.left, y), (b.right, y))
            across = True
        elif a.left < b.right and b.left < a.right:                     # 縦に向き合う
            x = (max(a.left, b.left) + min(a.right, b.right)) // 2
            start, end = ((x, a.bottom), (x, b.top)) if a.bottom <= b.top else ((x, a.top), (x, b.bottom))
            across = False
        else:
            raise PageTypeError(f"{where}: {ends[0]!r} and {ends[1]!r} do not face each other across a row or a "
                                "column — a link joins cells side by side or one above the other")
        between = Rect(min(start[0], end[0]), min(start[1], end[1]),
                       abs(end[0] - start[0]), abs(end[1] - start[1]))
        others = [other for other in every if other not in (a, b) and other not in blank
                  and not other.contains(a) and not other.contains(b)]
        for other in others:
            if (other.left < between.right and between.left < other.right
                    and other.top < between.bottom and between.top < other.bottom):
                raise PageTypeError(f"{where}: another cell stands between {ends[0]!r} and {ends[1]!r} — "
                                    "a link joins cells with nothing between them")
        page.line(start, end, arrow=True, tone=tone)
        if words:
            reach = max(rect.right for rect in every)
            _words_by(page, words.strip(), start, end, across, (a, b), others, reach, where)


def _words_by(page: Page, words: str, start: tuple[int, int], end: tuple[int, int], across: bool,
              ends: tuple[Rect, Rect], others: list[Rect], reach: int, where: str) -> None:
    """The words of a link: above a sideways arrow, to the right of a downward one.

    上は、矢印の上の隙間 (= 向き合う 2 つのマスの上端まで)、右は、矢印の右の隙間 (= 別のマスに突き当たるか、
    マスの並びの右端 `reach` まで)。言葉は隙間の中に、折って置く (= 本文の大きさの太字)。**隙間に入らなければ
    縮めずに止まる** ― 隙間を広げるのは使い方の `gap_m`。
    言葉の見た目は矢印の色 (`tone`) とは別 (= 本文の大きさ・太字・本文の色)。
    """
    s, ty = page.theme.spacing, page.theme.type
    if across:
        left, right = sorted((start[0], end[0]))
        bottom = start[1] - s.gap_s // 2
        room = bottom - max(rect.top for rect in ends)
        at, fix, align = "above the arrow, between the two cells", "a wider gap (= `gap_m` of the page's use)", "center"
    else:
        above, below = sorted((start[1], end[1]))
        stops = [rect.left for rect in others if rect.left >= start[0] and rect.top < below and above < rect.bottom]
        left = start[0] + s.gap_s
        right = min(stops) - s.gap_s if stops else reach
        room = below - above
        at, fix, align = ("to the right of the arrow, in the gap between the two cells",
                          "a taller gap (= `gap_m` of the page's use)", "left")
    usable = right - left - 2 * s.text_inset
    if usable < pt(ty.body):
        raise PageFullError(f"{where}: the words have {max(usable, 0)} EMU of width {at} — not even one character "
                            f"({pt(ty.body)}); {fix}, or no words")
    height = page.theme.wrapped_height(words, usable, ty.body, bold=True)
    if height > room:
        raise PageFullError(f"{where}: its words need {height} EMU of height {at} and there are {room} — "
                            f"{fix}, shorter words, or none; nothing will shrink")
    top = bottom - height if across else above + (room - height) // 2
    page.words(Rect(left, top, right - left, height), words, ty.body, bold=True, align=align)
