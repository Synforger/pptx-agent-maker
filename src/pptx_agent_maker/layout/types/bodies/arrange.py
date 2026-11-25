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
* **マスどうしの線 (`links`)** ― `compose` の頁で、`id` を付けたマスからマスへ矢印を引く。向き合うマス (= 縦か
  横の範囲が重なる) は真っすぐ、向き合わないマス (= 帯の違う箱どうしなど) は、箱をよけた直角の折れ線で結ぶ
  (= 曲がる回数が一番少ない道。真っすぐの線は相手の真ん中に立ち、同じ辺から出る曲がる線は 1 点から分かれ、交わる所は
  後の線が跳び越す。`link_routes`)。互いの出る箱から互いの入る箱への矢印も書かれている 2 本は、同じ隙間を離して
  並べずに 1 本に重ねて走る (= 重ねて読める結びが、全部書かれている)。
  入れ物 (`panel`) の中のマスと外のマスも結べ、入れ物そのものも端になる (= 入れ物とその中身は結べない)。
  色の役 (`tone`) と、矢印のそばに置く言葉 (`text`) も書ける (= 曲がる線の言葉は、出る辺から最初に曲がるまでの区間のそば)。
  出る辺 (`out`) と入る辺 (`in`) も書ける (= 書いた辺から出て、書いた辺へ入る。同じ箱の同じ辺から出る線が 2 本以上、
  または同じ辺へ入る線が 2 本以上なら、1 本の幹と横の線にまとまる。幹がほかの箱をよけて回る道は曲がる線と同じ)。
  線が `LINKS_FOR_A_DIAGRAM` 本以上で、結ぶ箱が `SPAN_FOR_A_DIAGRAM` 行以上かつ列以上に広がる頁は、形の図を持つ
  (= 条件で分かれる流れ図・泳ぎ線の図・つながりの図。一列の流れは数えない。`shows_a_diagram`)

⚠ **収まらなければ縮めずに止まる** (= どの並べ方も、箱か字を小さくして押し込むことはしない)。
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace
from typing import Sequence

from ...geometry import EMU_PER_CM, Rect, pt
from ...parts.page import Card, Page, PageFullError
from ..core.read import Spec, read_card, read_edge, read_tone, only_keys
from ..core.registry import PageTypeError
from ..core.stack import card_height
from .link_routes import (MAX_BENDS, SIDES, Attach, NoRoute, Point, Port, Room, Route, RouteSearch, edge_span, hops,
                          middle_ports, positions)

#: 跳び越しの半円の半径の下限 (= 矢印の線の太さの倍率)。既定の使い方では半径 (= `gap_s` の半分) が線の太さの
#: 約 2.8 倍で、交わりと読める。`gap_s` を詰めた使い方でも、その少し下までは小さくしない
HOP_LINES = 2.5
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
LINK_KEYS = ("from", "to", "text", "tone", "tentative", "out", "in")
#: 結んだ箱が形の図になる線の本数の下限 (= これより少ない線は、箱に添えた矢印)
LINKS_FOR_A_DIAGRAM = 3
#: 結んだ箱が形の図になる、広がりの行の数と列の数の下限 (= 一列の流れは、何本でも数えない)
SPAN_FOR_A_DIAGRAM = 2


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
    # 重なりは、形そのもので関係を見せる (= 文字の箱を線でつないだ輪や木とは違い、数える)
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
    named = s.gap_s + page.theme.caption_height(caption, right - left) if caption else 0
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


@dataclass(frozen=True)
class _Link:
    """One link as written, with the two rects it joins and how they stand to each other."""

    where: str
    ends: tuple[str, str]
    first: Rect
    second: Rect
    tone: str | None
    words: str | None
    #: "across" 横に向き合う / "down" 縦に向き合う / "" 向き合わない (= 曲がる線)
    facing: str
    #: 点線 (= 構想の段の流れ。カードの `tentative` と同じ書き方)
    dashed: bool = False
    #: 書いた出る辺・入る辺 (= `SIDES` の番号。書かなければ None で、道が選ぶ)
    out_side: int | None = None
    in_side: int | None = None

    def sides(self) -> tuple[int, int]:
        """The sides of the two rects a straight line leaves by and goes into (= indexes of `SIDES`)."""
        a, b = self.first, self.second
        if self.facing == "across":
            return (0, 2) if a.right <= b.left else (2, 0)
        return (1, 3) if a.bottom <= b.top else (3, 1)

    def overlap(self) -> tuple[int, int]:
        """Where the two rects face each other (= the coordinates along the edges, low then high)."""
        a, b = self.first, self.second
        if self.facing == "across":
            return max(a.top, b.top), min(a.bottom, b.bottom)
        return max(a.left, b.left), min(a.right, b.right)


def shows_a_diagram(link_count: int, boxes: Sequence[Rect]) -> bool:
    """Whether `link_count` lines joining `boxes` show a shape diagram, not words in boxes with arrows between them.

    Lines that run across both rows and columns show the relation by where the boxes stand, not by the words set
    side by side. A row (= a column) is a distinct top (= left) among the boxes.
    """
    return (link_count >= LINKS_FOR_A_DIAGRAM
            and len({box.top for box in boxes}) >= SPAN_FOR_A_DIAGRAM
            and len({box.left for box in boxes}) >= SPAN_FOR_A_DIAGRAM)


def links(page: Page, spec: Spec, written, cells: dict[str, Rect], every: list[Rect], blank: list[Rect],
          what: str) -> None:
    """An arrow from each cell named in `from` to the one in `to`: straight where the two face each other, round the cells in between where they do not.

    `detour` は頁のキーで、交わらない道を選んでよい長さの上限 (= 跳び越す道のうち一番短い道の何倍まで)。書かなければ
    上限は無く、交わらない道がいつも先 (= `link_routes.route_search` の順)。
    `every` は頁の全部のマス (= `id` の無いマスも)。線が別のマスを横切るなら止める (= 通れる道が無ければ、一番
    近い道がどのマスを横切るかを言う)。曲がる線は、マスどうしの間の空いた通り道を、曲がる回数の一番少ない道で
    通る (= `link_routes`)。
    ただし `blank` (= 中身の無いマス。`text = ""`) は空きなので数えない (= 離れた 2 つのマスを、間の空きを
    またいで結べる)。`tone` は矢印の色の役 (= 書かなければ灰)、`text` は矢印のそばの言葉 (= `_words_by`。曲がる線は
    最初の区間のそば)。`out` / `in` は出る辺・入る辺 (= `_bent_by_sides`: 書いた辺が真っすぐの線の辺と違う線と、同じ辺を
    分け合う線は折れ線になる)。
    結ぶ 2 つのマスの中身 (= 入れ物の中の段・札・字のマス) は、線がよける物に数えない (= 入れ物の縁へ入る最後の区間と、
    縁から出る最初の区間は、中のマスの手前を通るため)。ほかのマスは中身ごとよける。
    結んだマスが `shows_a_diagram` なら、形の図を持つ頁として宣言する (= `Page.drew_a_diagram`)。
    """
    if not isinstance(written, list) or not written:
        raise PageTypeError(f"{what}: `links` is a list of {{ from = \"id\", to = \"id\" }}")
    items = [_read_link(spec, item, number, cells, what) for number, item in enumerate(written, start=1)]
    detour = _read_detour(spec.get("detour"), what)
    s = page.theme.spacing
    room = Room(page.body, s.gap_x // 2, s.gap_y // 2, _hop(s))
    _clear_shared_words(items)
    items = _bent_by_sides(_facing_the_trunk(items))
    in_the_way = [[other for other in every if other not in (link.first, link.second) and other not in blank
                   and not other.contains(link.first) and not other.contains(link.second)
                   and not link.first.contains(other) and not link.second.contains(other)] for link in items]
    # 向き合っていても、真っすぐの線の上に別の箱が在れば、向き合わない 2 つと同じく折れ線で回る
    items = [replace(link, facing="") if link.facing and _blocked(link, _straight(link, sum(link.overlap()) // 2), others)
             else link for link, others in zip(items, in_the_way)]
    ports = _plan_ports(items, in_the_way, room, cells, detour)
    drawn: list[tuple[Point, ...]] = []
    drawn_ends: list[tuple[str, str]] = []
    written = {link.ends for link in items}
    reach = max(rect.right for rect in every)
    for number, (link, others) in enumerate(zip(items, in_the_way)):
        if link.facing:
            points, joined = _straight(link, ports[number]), (None, None)
            _clear_between(link, points[0], points[1], others, cells)
        else:
            kin = [line for line, ends in zip(drawn, drawn_ends) if _may_share(ends, link.ends, written)]
            route = _route(link, others, drawn, room, ports[number], cells, strict=True, kin=kin, detour=detour)
            points, joined = route.points, (_joined(link.first, route.start), _joined(link.second, route.end))
        page.line(points[0], points[-1], arrow=True, tone=link.tone, corners=points[1:-1], hops=hops(points, drawn, room.hop),
                  hop=room.hop, begins_on=joined[0], ends_on=joined[1], dashed=link.dashed)
        drawn.append(points)
        drawn_ends.append(link.ends)
        if link.words:
            end = points[-1] if link.facing else points[1]
            across = points[0][1] == end[1]
            _words_by(page, link.words.strip(), points[0], end, across,
                      _ceiling(page, link, points[0][1], sorted((points[0][0], end[0])), others) if across else 0,
                      others, reach, link.where, bent=not link.facing)
    if shows_a_diagram(len(items), [box for link in items for box in (link.first, link.second)]):
        page.drew_a_diagram()


def _written_edges(items: list[_Link]) -> tuple[Counter, Counter]:
    """How many links are written to leave each (cell, edge), and how many to enter each (cell, edge)."""
    return (Counter((link.ends[0], link.out_side) for link in items if link.out_side is not None),
            Counter((link.ends[1], link.in_side) for link in items if link.in_side is not None))


def _facing_the_trunk(items: list[_Link]) -> list[_Link]:
    """The links, each of those that part from a trunk given the edge facing the trunk to go into, where it wrote none.

    同じ箱の同じ辺から出ると書いた線が 2 本以上なら、`in` を書かない線は、幹に向いた辺 (= 出る辺の反対側。相手の箱が
    出る辺の向こうに在る時だけ) から入る。書かなければ、道が辺を選ぶので、横の辺から入る道を選ぶことがある。
    """
    leaving, _ = _written_edges(items)
    beyond = (lambda a, b: b.left >= a.right, lambda a, b: b.top >= a.bottom,
              lambda a, b: b.right <= a.left, lambda a, b: b.bottom <= a.top)
    return [replace(link, in_side=(link.out_side + 2) % 4)
            if (link.in_side is None and link.out_side is not None and leaving[(link.ends[0], link.out_side)] > 1
                and beyond[link.out_side](link.first, link.second)) else link for link in items]


def _bent_by_sides(items: list[_Link]) -> list[_Link]:
    """The links, each made a bent line when it is written to leave or enter by an edge a straight line would not use, or to leave (enter) by an edge together with another.

    向き合う 2 つの線は、書いた辺が真っすぐの線の辺と同じなら真っすぐのまま (= 書かなかった線の座標は変わらない)。
    同じ箱の同じ辺から出る (= 同じ辺へ入る) と書いた線が 2 本以上なら、向き合う線も折れ線で結ぶ (= 1 本の幹から横の線を
    通って分かれる形。真っすぐな線が混ざると、幹から出る線と離れて出る線が並ぶ)。
    """
    leaving, entering = _written_edges(items)

    def bends(link: _Link) -> bool:
        if not link.facing:
            return False
        out_side, in_side = link.sides()
        leaves_otherwise = link.out_side is not None and (
            link.out_side != out_side or leaving[(link.ends[0], link.out_side)] > 1)
        enters_otherwise = link.in_side is not None and (
            link.in_side != in_side or entering[(link.ends[1], link.in_side)] > 1)
        return leaves_otherwise or enters_otherwise

    return [replace(link, facing="") if bends(link) else link for link in items]


def _clear_shared_words(items: list[_Link]) -> None:
    """Stop the page when words are written on a line that leaves an edge together with others: its first run is theirs too."""
    leaving, _ = _written_edges(items)
    for link in items:
        if link.words and link.out_side is not None and leaving[(link.ends[0], link.out_side)] > 1:
            raise PageTypeError(
                f"{link.where}: this line leaves {link.ends[0]!r} by its {SIDES[link.out_side]} edge together with "
                f"{leaving[(link.ends[0], link.out_side)] - 1} other line(s), so the run it starts with is one they share "
                "and words beside it would read as the words of all of them — drop `text` on it, or let it leave by an "
                "edge of its own")


def _may_share(ends: tuple[str, str], link_ends: tuple[str, str], written: set[tuple[str, str]]) -> bool:
    """Whether a line drawn between the cells `ends` may share runs with the line being found between `link_ends`.

    重ねた区間は、片方の出る箱からもう片方の入る箱への結びとも読める。分け合ってよいのは、そう読める結び (= 互いの
    出る箱から互いの入る箱への矢印) がどちらも書かれている時。出る箱か入る箱が同じ 2 本は、読める結びが自分たち
    そのものなので、いつも当たる (= 1 点から分かれる枝と、1 点へ集まる合流)。
    """
    return {(ends[0], link_ends[1]), (link_ends[0], ends[1])} <= written


def _read_link(spec: Spec, item, number: int, cells: dict[str, Rect], what: str) -> _Link:
    """One written link, checked: both ends known, neither holding the other, a tone that exists, edges that are edges."""
    where = f"{what}: link {number}"
    only_keys(item, set(LINK_KEYS), where)
    ends = [str(item.get(key, "")) for key in ("from", "to")]
    missing = [end for end in ends if end not in cells]
    if missing:
        known = ", ".join(sorted(cells)) or "none — give the cells an `id`"
        raise PageTypeError(f"{where}: no cell has the id {missing[0]!r} (= the ids on this page: {known})")
    tone = read_tone(spec, item, where, "box") if "tone" in item else None
    dashed = item.get("tentative", False)
    if not isinstance(dashed, bool):
        raise PageTypeError(f"{where}: `tentative` is true or false (= a dotted line), not {dashed!r}")
    out_side, in_side = (None if edge is None else SIDES.index(edge) for edge in
                         (read_edge(item, "out", where), read_edge(item, "in", where)))
    words = item.get("text")
    if "text" in item and (not isinstance(words, str) or not words.strip()):
        raise PageTypeError(f"{where}: `text` is the words set beside the arrow, not {words!r} — "
                            "drop the key for an arrow without words")
    a, b = cells[ends[0]], cells[ends[1]]
    if a.contains(b) or b.contains(a):
        holder, held = (ends[0], ends[1]) if a.contains(b) else (ends[1], ends[0])
        raise PageTypeError(f"{where}: {holder!r} holds {held!r} — a link joins two cells side by side or one "
                            "above the other, not a cell and what stands inside it")
    if a.top < b.bottom and b.top < a.bottom:
        facing = "across"
    elif a.left < b.right and b.left < a.right:
        facing = "down"
    else:
        facing = ""
    return _Link(where, (ends[0], ends[1]), a, b, tone, words, facing, dashed, out_side, in_side)


def _plan_ports(items: list[_Link], in_the_way: list[list[Rect]], room: Room, cells: dict[str, Rect],
                detour: float | None) -> dict:
    """Where each line leaves and enters: the coordinate along the edge for a straight line, a port pair for a bent one.

    道を一度、辺の真ん中から出入りするものとして決め (= どの辺を使うかを知るため)、線ごとの出入りの位置を決める
    (= `link_routes.positions`)。
    """
    drawn: list[tuple[Point, ...]] = []
    attaches: list[Attach] = []
    chosen: dict[int, Route] = {}
    straights: dict[int, tuple[int, int]] = {}
    for number, (link, others) in enumerate(zip(items, in_the_way)):
        if link.facing:
            low, high = link.overlap()
            straights[number] = (low, high)
            drawn.append(_straight(link, (low + high) // 2))
            side_a, side_b = link.sides()
            attaches += [Attach(number, False, link.first, side_a), Attach(number, True, link.second, side_b)]
            continue
        route = _route(link, others, drawn, room, None, cells, strict=False, detour=detour)
        chosen[number] = route
        drawn.append(route.points)
        attaches += [_attach(number, False, link.first, route.start.side, route.points),
                     _attach(number, True, link.second, route.end.side, route.points[::-1])]
    coordinates = positions(attaches, straights, 2 * room.hop)
    ports: dict = {}
    for number, link in enumerate(items):
        if link.facing:
            ports[number] = coordinates[(number, False)]
            continue
        route = chosen[number]
        ports[number] = (_port_at(link.first, route.start.side, coordinates[(number, False)]),
                         _port_at(link.second, route.end.side, coordinates[(number, True)]))
    for number, link in enumerate(items):
        if not link.facing:
            ports[number] = _apart_if_fewer_bends(number, link, ports[number], in_the_way[number], room, attaches,
                                                  coordinates, 2 * room.hop)
    return ports


def _apart_if_fewer_bends(number: int, link: _Link, shared: tuple[Port, Port], others: list[Rect], room: Room,
                          attaches: list[Attach], coordinates: dict[tuple[int, bool], int], clear: int) -> tuple[Port, Port]:
    """The ports of a bent line: those `positions` gave it, or a point of its own on the same edge where sharing costs bends.

    端の点を別の線と分け合う (= 幹から分かれる・合流する) と、その点へ寄るために曲がりが増えることがある。分け合う点で
    引いた道より、同じ辺の空いた点 (= 辺を等しく割った点のうち、ほかの線の端から `clear` 以上離れた物) で引いた道の方が
    曲がりが少ない時だけ、その端を空いた点へ離す。曲がりが同じなら分け合ったまま (= 幹の形を保つ)。
    """
    ends = []
    for last, port, box in ((False, shared[0], link.first), (True, shared[1], link.second)):
        near = [coordinates[(each.link, each.last)] for each in attaches
                if each.box == box and each.side == port.side and (each.link, each.last) != (number, last)]
        at = coordinates[(number, last)]
        if at not in near:
            ends.append([port])
            continue
        start, end = edge_span(box, port.side)
        steps = [start + (end - start) * n // (len(near) + 2) for n in range(1, len(near) + 2)]
        ends.append([_port_at(box, port.side, step) for step in steps
                     if all(abs(step - other) >= clear for other in near)] or [port])
    if ends == [[shared[0]], [shared[1]]]:
        return shared
    try:
        joined = RouteSearch(link.first, link.second, others, [], room, [shared[0]], [shared[1]], strict=False).cheapest()
        apart = RouteSearch(link.first, link.second, others, [], room, ends[0], ends[1], strict=False).cheapest()
    except NoRoute:
        return shared
    if apart.blocked or (not joined.blocked and apart.bends >= joined.bends):
        return shared
    return apart.start, apart.end


def _attach(link: int, last: bool, box: Rect, side: int, points: tuple[Point, ...]) -> Attach:
    """How a bent line stands at one end: the side it uses, and the way it first turns along that side."""
    (x0, y0), (x1, y1) = points[1], points[2] if len(points) > 2 else points[1]
    along = (y1 - y0) if side % 2 == 0 else (x1 - x0)
    return Attach(link, last, box, side, (along > 0) - (along < 0))


def _joined(box: Rect, port: Port) -> tuple[Rect, int] | None:
    """The box and the side a line is to be attached to: only where it meets the middle of the edge (= the box's connection point)."""
    return (box, port.side) if port in middle_ports(box) else None


def _ports_on(box: Rect, side: int | None) -> list[Port]:
    """The ports in the middle of a box's edges: the one on `side`, or all four when no side is written."""
    return [port for port in middle_ports(box) if side is None or port.side == side]


def _port_at(box: Rect, side: int, along: int) -> Port:
    """The port on a side of a box at a coordinate along the edge."""
    return Port(((box.right, along), (along, box.bottom), (box.left, along), (along, box.top))[side], side)


def _route(link: _Link, others: list[Rect], drawn: list[tuple[Point, ...]], room: Room, ports, cells: dict[str, Rect],
           *, strict: bool, kin: Sequence[tuple[Point, ...]] = (), detour: float | None = None) -> Route:
    """The cheapest path for a line that bends; it stops the page, saying what it runs across, when every way is shut.

    `detour` が在れば、交わらない道が、跳び越す道のうち一番短い道の `detour` 倍より長い時に、その跳び越す道を選ぶ。
    """
    starts, ends = ((_ports_on(link.first, link.out_side), _ports_on(link.second, link.in_side)) if ports is None
                    else ([ports[0]], [ports[1]]))
    try:
        route = RouteSearch(link.first, link.second, others, drawn, room, starts, ends, strict=strict, kin=kin).cheapest()
        if detour is not None and not route.blocked:
            short = RouteSearch(link.first, link.second, others, drawn, room, starts, ends, strict=strict, kin=kin,
                                crossing_first=False).cheapest()
            if not short.blocked and short.touching <= route.touching and route.length > detour * short.length:
                route = short
    except NoRoute as reason:
        raise PageTypeError(f"{link.where}: the line from {link.ends[0]!r} to {link.ends[1]!r} has no room to leave "
                            f"{link.ends[0]!r} and reach {link.ends[1]!r} — {reason}") from reason
    if route.blocked:
        a, b = link.ends
        raise PageTypeError(
            f"{link.where}: the line from {a!r} to {b!r} finds no way through ({MAX_BENDS} bends at most; the nearest "
            f"leaves {a!r} by its {SIDES[route.start.side]} edge, bends {route.bends} time(s) and goes into {b!r} by its "
            f"{SIDES[route.end.side]} edge) and runs across {_called_all(route.blocked, cells)} — move the cells so "
            "nothing stands on its path")
    return route


def _hop(s) -> int:
    """The radius of the half circle a line hops another with: half `gap_s`, no smaller than `HOP_LINES` arrow lines, and no wider than the room a line keeps from a box (= the half circle stays off the boxes)."""
    return min(max(s.gap_s // 2, round(HOP_LINES * s.arrow_line)), s.gap_x // 2, s.gap_y // 2)


def _read_detour(value, what: str) -> float | None:
    """The page's `detour`, checked: a number of 1 or more, or nothing."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 1:
        raise PageTypeError(f"{what}: `detour` is how many times as long as the shortest way that hops a line a way "
                            f"round may be — a number of 1 or more, not {value!r}")
    return float(value)


def _straight(link: _Link, along: int) -> tuple[Point, Point]:
    """The two ends of the straight line between two cells that face each other, `along` the edges."""
    side_a, side_b = link.sides()
    return _port_at(link.first, side_a, along).point, _port_at(link.second, side_b, along).point


def _blocked(link: _Link, ends: tuple[Point, Point], others: list[Rect]) -> bool:
    """Whether a cell stands on the straight line between two cells that face each other."""
    (x1, y1), (x2, y2) = ends
    between = Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
    return any(other.left < between.right and between.left < other.right
               and other.top < between.bottom and between.top < other.bottom for other in others)


def _clear_between(link: _Link, start: Point, end: Point, others: list[Rect], cells: dict[str, Rect]) -> None:
    """Stop the page when a cell stands on the straight line between two cells that face each other."""
    if _blocked(link, (start, end), others):
        raise PageTypeError(f"{link.where}: another cell stands between {link.ends[0]!r} and {link.ends[1]!r} — "
                            "a link joins cells with nothing between them")


def _called_all(rects: tuple[Rect, ...], cells: dict[str, Rect]) -> str:
    """How a message names the cells a line runs across, one or several."""
    return " and ".join(_called(rect, cells) for rect in rects)


def _called(rect: Rect, cells: dict[str, Rect]) -> str:
    """How a message names a cell: by its id when it has one, else by where it stands on the slide."""
    named = [name for name, found in cells.items() if found == rect]
    if named:
        return f"the cell {named[0]!r}"
    return f"a cell with no id ({rect.left / EMU_PER_CM:.1f} cm from the left, {rect.top / EMU_PER_CM:.1f} cm from the top)"


def _gap_to_widen(page: Page, gap: str) -> str:
    """The distance of the page's use that makes room for words: `gap` when the use writes it, else `gap_m` (= which the gaps follow)."""
    return f"`{gap}`" if gap in dict(page.theme.type.spaced) else "`gap_m`"


def _ceiling(page: Page, link: _Link, along: int, span: list[int], others: list[Rect]) -> int:
    """How high the words above a sideways run (at `along`, over `span`) may stand.

    向き合う 2 つのマスの間の真っすぐな線は、2 つのマスの上端まで (= 隙間の高さ)。曲がる線の最初の区間は、出るマスの
    横の空いた所を走るので、上は、その区間の上に在る別のマスの下端か、頁の本体の上端まで。
    """
    if link.facing:
        return max(link.first.top, link.second.top)
    above = [rect.bottom for rect in (*others, link.second) if rect.bottom <= along and rect.left < span[1] and span[0] < rect.right]
    return max([page.body.top, *above])


def _words_by(page: Page, words: str, start: tuple[int, int], end: tuple[int, int], across: bool,
              ceiling: int, others: list[Rect], reach: int, where: str, *, bent: bool = False) -> None:
    """The words of a link: above a sideways arrow, to the right of a downward one.

    上は、矢印の上の隙間 (= 向き合う 2 つのマスの上端まで)、右は、矢印の右の隙間 (= 別のマスに突き当たるか、
    マスの並びの右端 `reach` まで)。言葉は隙間の中に、折って置く (= 本文の大きさの太字)。**隙間に入らなければ
    縮めずに止まる** ― 隙間を広げるのは使い方の `gap_x` (= 横の矢印) か `gap_y` (= 縦の矢印)。使い方が
    それを書いていなければ `gap_m` (= 2 つの間はそれに従う)。縦の矢印の右に字の幅が 1 文字ぶんも無い時は、足りないのは
    高さでなく幅で、決めるのは隣のマスとの間 (= `gap_x`)・字が矢印と隣のマスから離れる距離 (= `gap_s`)・列の幅。
    言葉の見た目は矢印の色 (`tone`) とは別 (= 本文の大きさ・太字・本文の色)。曲がる線 (`bent`) は、出る辺から
    最初に曲がるまでの区間 (= `start` から `end`) のそばに置く。
    """
    s, ty = page.theme.spacing, page.theme.type
    if across:
        left, right = sorted((start[0], end[0]))
        bottom = start[1] - s.gap_s // 2
        room = bottom - ceiling
        at, align = "above the arrow, between the two cells", "center"
        fix = f"a wider gap (= {_gap_to_widen(page, 'gap_x')} of the page's use)"
        if bent:
            at = "above the first run of the line, out of the cell it leaves"
            fix = f"more room above that run (= a taller gap there, {_gap_to_widen(page, 'gap_y')} of the page's use)"
    else:
        above, below = sorted((start[1], end[1]))
        stops = [rect.left for rect in others if rect.left >= start[0] and rect.top < below and above < rect.bottom]
        left = start[0] + s.gap_s
        right = min(stops) - s.gap_s if stops else reach
        room = below - above
        at, fix, align = ("to the right of the arrow, in the gap between the two cells",
                          f"a taller gap (= {_gap_to_widen(page, 'gap_y')} of the page's use)", "left")
        if bent:
            at = "to the right of the first run of the line, out of the cell it leaves"
    usable = right - left - 2 * s.text_inset
    if usable < pt(ty.body):
        if not across:
            at = "to the right of the arrow, up to the cell beside it"
            fix = (f"a wider gap to the cell beside it (= {_gap_to_widen(page, 'gap_x')} of the page's use), a smaller "
                   "`gap_s` (= what the words keep from the arrow and from that cell), or a wider column")
        raise PageFullError(f"{where}: the words have {max(usable, 0)} EMU of width {at} — not even one character "
                            f"({pt(ty.body)}); {fix}, or no words")
    height = page.theme.wrapped_height(words, usable, ty.body, bold=True)
    if height > room:
        raise PageFullError(f"{where}: its words need {height} EMU of height {at} and there are {room} — "
                            f"{fix}, shorter words, or none; nothing will shrink")
    top = bottom - height if across else above + (room - height) // 2
    page.words(Rect(left, top, right - left, height), words, ty.body, bold=True, align=align)
