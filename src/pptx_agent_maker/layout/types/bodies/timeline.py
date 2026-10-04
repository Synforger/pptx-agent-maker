"""Periods left to right, lanes top to bottom, bars and marks on the lanes.

組むのは 3 段:

* **読む** (`_read`) ― 書かれた物を、文字の大きさにも頁の広さにも依らない形で 1 度だけ
* **測る** (`_measure`) ― 文字の大きさを 1 つ決めて、段と高さと名前の側を。収まらなければ止まる
* **置く** (`_place`) ― 上から帯を取り、その中を割る

横の位置を決めるのは `_Plot` 1 つ (= 期間の番号から横の位置、名前を隣に出せる側、レーンの高さ)。
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real

from ...base.geometry import Rect
from ...base.tokens import Theme
from ...parts.look import Style, TONES
from ...parts.page import Page, PageFullError
from ..core.read import LOOK_KEYS, Spec, only_keys, read_style, read_tone
from ..core.registry import PageTypeError, register


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
    point: bool = False
    row: int = 0
    #: 棒が書いた見た目 (= 地が空ならレーンの色)
    style: Style = Style(tone="")

    def room(self, gap: int) -> tuple[int, int]:
        """What it keeps clear of its neighbours: itself, and its name when that sits beside it."""
        start = self.left - (gap + self.wide + gap if self.side == "left" else 0)
        end = self.right + (gap + self.wide + gap if self.side == "right" else 0)
        return start, end

    def style_on(self, lane: str) -> Style:
        """How it is painted on a lane of this tone: its own ground if it wrote one, else the lane's."""
        return Style(self.style.tone or lane, self.style.icon, self.style.tentative, self.style.strong)


@dataclass(frozen=True)
class _Written:
    """One bar as the manifest wrote it, read once (= positions do not depend on the type size)."""

    what: str
    start: float
    end: float
    text: str
    #: 覆うレーンの数 (= `spans`。書かなければ 1)
    reach: int
    #: 地が空なら「書かれていない」(= レーンの色)
    style: Style


@dataclass(frozen=True)
class _Lane:
    """One lane as the manifest wrote it."""

    name: str
    tone: str
    bars: list[_Written]
    #: 印 (= 何番目の印か, 時点, 名前)
    marks: list[tuple[str, float, str]]
    #: またがる棒がこのレーンを覆う時期 (= ここから出る棒と、上のレーンから降りてくる棒)
    walls: list[tuple[float, float, str]]


@dataclass(frozen=True)
class _Plan:
    """Everything a timeline was written with (= none of it depends on the type size)."""

    periods: list[str]
    #: 期間の上に掛ける帯 (= 始まり, 終わり, 名前)。始まりの順
    phases: list[tuple[float, float, str]]
    #: 全レーンを貫く日付 (= 時点, 名前)
    dates: list[tuple[float, str]]
    lanes: list[_Lane]


@dataclass
class _Packed:
    """One lane measured at one type size: its pieces in rows, and how tall each row stands."""

    name: str
    name_tall: int
    pieces: list[_Piece]
    heights: list[int]
    tone: str


@dataclass(frozen=True)
class _Layout:
    """A timeline measured at one type size, ready to be placed."""

    size: float
    line: int
    #: 棒 1 段・期間の枠 1 つの高さ
    cell: int
    span_height: int
    stones: list[_Piece]
    stone_rows: int
    packed: list[_Packed]
    #: またがる棒 (= 出るレーンの番号, 覆うレーンの数, 棒)
    across: list[tuple[int, int, _Piece]]
    wanted: int


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


class _Plot:
    """Where things go across a timeline: a period number to a place, and the side a name fits on."""

    def __init__(self, theme: Theme, area: Rect, plan: _Plan) -> None:
        s = theme.spacing
        self.theme, self.area, self.count = theme, area, len(plan.periods)
        # 左にレーンの名前、右に時間。名前の列は一番長い名前ぶんで、取りすぎるなら折り返させる。
        # 時間の側は印の半分だけ内へ寄せる (= 端の時点に置いた印が枠から出ない)
        self.lane_size = theme.type.stage
        widest = max(theme.width(lane.name, self.lane_size, bold=True) for lane in plan.lanes)
        name_width = min(widest + s.gap_s, area.width // 4)
        self.names, self.column = area.columns([name_width, area.width - name_width], gap=s.gap_s)
        self.time = self.column.inset(x=s.mark // 2)
        #: 頁を横切る日付の線の位置
        self.crossing = [self.at(position) for position, _text in plan.dates]

    def at(self, position: float) -> int:
        return self.time.span(0, position / self.count).right

    def beside(self, left: int, right: int, wide: int, walls=()) -> str | None:
        """Which side of something a name of this width can go on, if either.

        右が先。ただし日付の線が名前を貫く側は、貫かれない側が在ればそちらへ譲る。
        `walls` はそのレーンを覆うまたがる棒の左右 ― 名前はその上へは出せない。
        """
        s = self.theme.spacing
        fits = []
        if right + s.gap_s + wide <= self.column.right:
            fits.append(("right", right + s.gap_s, right + s.gap_s + wide))
        if left - s.gap_s - wide >= self.column.left:
            fits.append(("left", left - s.gap_s - wide, left - s.gap_s))
        fits = [(side, start, end) for side, start, end in fits
                if not any(start < wall_right + s.gap_s and wall_left - s.gap_s < end
                           for wall_left, wall_right in walls)]
        clear = [side for side, start, end in fits if not any(start < x < end for x in self.crossing)]
        return (clear or [side for side, _start, _end in fits] or [None])[0]

    def over(self, band: Rect, start: float, end: float) -> Rect:
        """The part of a band over a stretch of periods, drawn in by the gap bars keep."""
        return Rect(self.time.left, band.top, self.time.width, band.height) \
            .span(start / self.count, end / self.count).inset(x=self.theme.spacing.bar_gap)

    def lane_height(self, name_tall: int, heights: list[int], extra: int = 0) -> int:
        # レーンの上下の余白は段の間と同じ幅 (= 区切りの線が在るので、広く空けなくても分かれる。
        # 広く取ると、文字を大きくしたぶん載るレーンが減る)
        s = self.theme.spacing
        stack = sum(tall + extra for tall in heights) + s.row_gap * (len(heights) - 1)
        return max(stack, name_tall) + 2 * s.row_gap

    def reaches(self, packed: list[_Packed], first: int, last: int, extra: int = 0,
                top: int = 0) -> tuple[int, int]:
        """From the top of lane `first`'s first row to the bottom of lane `last`'s last row.

        `top` はレーンの並びの上端 (= 測るだけなら 0 でよい。置くときは最初のレーンの上端)。
        """
        s = self.theme.spacing
        starts = [top]
        for lane in packed:
            starts.append(starts[-1] + self.lane_height(lane.name_tall, lane.heights, extra))
        heights = packed[last].heights
        stack = sum(tall + extra for tall in heights) + s.row_gap * (len(heights) - 1)
        return starts[first] + s.row_gap, starts[last] + s.row_gap + stack


def _read(spec: Spec) -> _Plan:
    """What the manifest wrote, checked: periods, phases, dates, and each lane with its bars and marks."""
    periods = [str(period) for period in spec.get("periods") or []]
    lanes = spec.get("lanes") or []
    if not periods:
        raise PageTypeError("timeline: `periods` is empty — a timeline needs its periods")
    if not lanes:
        raise PageTypeError("timeline: `lanes` is empty — a timeline needs at least one lane")
    count = len(periods)
    misplaced = (" `phases` and `milestones` belong to the page: in TOML, write them above the "
                 "first `[[pages.lanes]]`.")

    spans = []
    for index, phase in enumerate(spec.get("phases") or [], start=1):
        only_keys(phase, {"from", "to", "label"}, f"timeline: phase {index}")
        start, end = _stretch(phase, count, f"phase {index}")
        spans.append((start, end, str(phase.get("label", ""))))
    spans.sort()
    for (_s, before, _l), (after, _e, label) in zip(spans, spans[1:]):
        if after < before:
            raise PageTypeError(f"timeline: phase {label!r} starts before the one before it ends")
    dates = []
    for index, stone in enumerate(spec.get("milestones") or [], start=1):
        only_keys(stone, {"at", "text"}, f"timeline: milestone {index}")
        dates.append((_position(stone, "at", count, f"milestone {index}"), str(stone.get("text", ""))))
    read = []
    # レーンごとの、またがる棒が覆う時期 (= そのレーンから出る棒と、上のレーンから降りてくる棒)
    covered: list[list[tuple[float, float, str]]] = [[] for _lane in lanes]
    for index, lane in enumerate(lanes, start=1):
        only_keys(lane, {"name", "bars", "marks", "tone"}, f"timeline: lane {index}", misplaced)
        bars, marks = [], []
        for number, bar in enumerate(lane.get("bars") or [], start=1):
            what = f"lane {index}, bar {number}"
            only_keys(bar, {"from", "to", "text", "spans", *LOOK_KEYS}, f"timeline: {what}")
            start, end = _stretch(bar, count, what)
            reach = _reach(bar, len(lanes) - index + 1, what)
            # 地を書かなかった棒は空のまま持つ (= レーンの色。置くときに決まる)
            bars.append(_Written(what, start, end, str(bar.get("text", "")), reach,
                                 read_style(spec, bar, f"timeline: {what}", "")))
            if reach > 1:
                for under in range(index - 1, index - 1 + reach):
                    covered[under].append((start, end, what))
        for number, mark in enumerate(lane.get("marks") or [], start=1):
            what = f"lane {index}, mark {number}"
            only_keys(mark, {"at", "text"}, f"timeline: {what}")
            marks.append((what, _position(mark, "at", count, what), str(mark.get("text", ""))))
        # 色の役を書いたレーンはその色、書かなければ 2 つの薄い地の交互 (= 隣と見分けるだけ)
        tone = read_tone(spec, lane, f"timeline: lane {index}", TONES[(index - 1) % 2])
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
            for written in bars:
                other, other_start, other_end = written.what, written.start, written.end
                if written.reach == 1 and start < other_end and other_start < end:
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
    return _Plan(periods, spans, dates,
                 [_Lane(name, tone, bars, marks, walls)
                  for (name, tone, bars, marks), walls in zip(read, covered)])


def _measure(plot: _Plot, plan: _Plan, size: float) -> _Layout:
    """Everything measured at one type size, or PageFullError when the page cannot hold it."""
    theme, s, count = plot.theme, plot.theme.spacing, plot.count
    line = theme.line_height(size)
    cell = line + 2 * s.bar_pad_y          # 棒 1 段・期間の枠 1 つの高さ

    span_height = 0
    for start, end, label in plan.phases:
        inner = plot.at(end) - plot.at(start) - 2 * (s.bar_gap + s.bar_pad_x)
        span_height = max(span_height, theme.wrapped_height(label, max(inner, 1), size)
                          + 2 * s.bar_pad_y)
    for index, period in enumerate(plan.periods):
        inner = plot.at(index + 1) - plot.at(index) - 2 * (s.bar_gap + s.bar_pad_x)
        if theme.width(period, size, bold=True) > inner:
            raise PageFullError(
                f"the period name {period!r} is wider than one of {count} columns at "
                f"{size:g}pt — shorter names, or fewer periods on this page; it will not shrink")

    stones = []
    for where, text in zip(plot.crossing, (text for _p, text in plan.dates)):
        wide = theme.width(text, size, bold=True)
        side = plot.beside(where, where, wide)
        if side is None:
            raise PageFullError(f"the milestone name {text!r} is wider than the timeline itself")
        stones.append(_Piece(where, where, text, side, line, wide))
    stone_rows = _flags(stones, s.bar_pad_x)

    packed = []
    across = []                            # またがる棒 (= 出るレーンの番号, 覆うレーンの数, 棒)
    for number, lane in enumerate(plan.lanes):
        walls = [(plot.at(start) + s.bar_gap, plot.at(end) - s.bar_gap) for start, end, _what in lane.walls]
        pieces = []
        for written in lane.bars:
            what, text, reach, icon = written.what, written.text, written.reach, written.style.icon
            left, right = plot.at(written.start) + s.bar_gap, plot.at(written.end) - s.bar_gap
            if right <= left:
                raise PageFullError(f"{what} is too short a stretch to draw at this scale")
            # アイコンは名前の前に字の高さで置く (= 棒の中に、名前が隣へ出る時も)
            lead = line + s.gap_s if icon else 0
            if icon and right - left < line + 2 * s.bar_pad_x:
                raise PageFullError(
                    f"{what} is too short for its icon at {size:g}pt — a longer stretch, or no icon")
            wide, inner = theme.width(text, size), right - left - 2 * s.bar_pad_x - lead
            if reach > 1:
                # 名前はいつも棒の中 (= 隣へ出すと、覆うレーン全部でその場所を空けることになる)。
                # 棒が高いので、折れる行は中に収まる
                lines = 1 if wide <= inner else theme.wraps(text, max(inner, 1), size)
                across.append((number, reach, _Piece(left, right, text, "in",
                                                     lines * line + 2 * s.bar_pad_y, wide,
                                                     style=written.style)))
                continue
            if wide <= inner:
                side, lines = "in", 1
            elif theme.unbreakable(text, size) <= inner and theme.wraps(text, inner, size) == 2:
                side, lines = "in", 2      # 語の切れ目で 2 行に収まる (= 語の途中では折らない)
            elif plot.beside(left, right, wide, walls):
                side, lines = plot.beside(left, right, wide, walls), 1
            else:
                side, lines = "in", theme.wraps(text, max(inner, 1), size)
            pieces.append(_Piece(left, right, text, side, lines * line + 2 * s.bar_pad_y, wide,
                                 style=written.style))
        for what, position, text in lane.marks:
            where = plot.at(position)
            left, right = where - s.mark // 2, where - s.mark // 2 + s.mark
            wide = theme.width(text, size)
            side = plot.beside(left, right, wide, walls)
            if side is None and plot.beside(left, right, wide) is not None:
                raise PageFullError(
                    f"the name of {what} ({text!r}) has no room beside it: a bar spanning "
                    "this lane stands on either side it could go — a shorter name, or move "
                    "the mark; it will not shrink")
            if side is None:
                raise PageFullError(
                    f"the name of {what} ({text!r}) is wider than the timeline itself")
            pieces.append(_Piece(left, right, text, side, max(s.mark, cell), wide, point=True))
        name_tall = theme.wrapped_height(lane.name, plot.names.width, plot.lane_size, bold=True)
        rows = _rows(pieces, s.gap_s)
        # 自分の物を持たないレーン (= 上から降りてくる棒に覆われるだけ) も 1 段ぶんは取る
        heights = [max(p.tall for p in pieces if p.row == row) for row in range(rows)] or [cell]
        packed.append(_Packed(lane.name, name_tall, pieces, heights, lane.tone))

    # またがる棒の名前が、覆うレーンを合わせた高さに収まらなければ、出るレーンの 1 段目を
    # そのぶん高くする (= 縮めない、切らない)
    for number, reach, piece in across:
        top, bottom = plot.reaches(packed, number, number + reach - 1)
        if piece.tall > bottom - top:
            packed[number].heights[0] += piece.tall - (bottom - top)

    head = (span_height + s.row_gap if plan.phases else 0) + cell + s.gap_s \
        + (stone_rows * line + s.gap_s if stones else 0)
    wanted = head + sum(plot.lane_height(lane.name_tall, lane.heights) for lane in packed)
    if wanted > plot.area.height:
        raise PageFullError(
            f"this timeline needs {wanted} EMU of height at {size:g}pt and the body has "
            f"{plot.area.height} — fewer lanes, shorter names, or two pages; it will not shrink")
    return _Layout(size, line, cell, span_height, stones, stone_rows, packed, across, wanted)


def _place(page: Page, plot: _Plot, plan: _Plan, layout: _Layout) -> None:
    """Put a measured timeline on the page: bands off the top, then everything inside them."""
    s, area, count = page.theme.spacing, plot.area, plot.count
    size, line, cell, packed = layout.size, layout.line, layout.cell, layout.packed
    extra = min((area.height - layout.wanted) // sum(len(lane.heights) for lane in packed),
                round(cell * ROOMY))

    # -- 置く (= 上から帯を取り、その中を割る) -------------------------------------
    rest = area
    span_band = None
    if plan.phases:
        span_band, rest = rest.split_top(layout.span_height, gap=s.row_gap)
    period_band, rest = rest.split_top(cell, gap=s.gap_s)
    flags_top = rest.top
    if layout.stones:
        _band, rest = rest.split_top(layout.stone_rows * line, gap=s.gap_s)
    bands = []
    for lane in packed:
        band, rest = rest.split_top(plot.lane_height(lane.name_tall, lane.heights, extra))
        bands.append(band)
    lanes_top, lanes_bottom = bands[0].top, bands[-1].bottom

    # 下に敷く物から先に置く: 列の地 → 期間の境 → レーンの区切り → 頁を横切る日付の線
    # (= 線を棒の上に引くと、棒の名前を貫く)
    for index in range(1, count, 2):
        page.stripe(Rect(plot.at(index), period_band.bottom, plot.at(index + 1) - plot.at(index),
                         lanes_bottom - period_band.bottom))
    for index in range(count + 1):
        page.rule(Rect(plot.at(index) - s.hairline // 2, period_band.bottom, s.hairline,
                       lanes_bottom - period_band.bottom), weight="firm")
    for edge in [band.top for band in bands] + [lanes_bottom - s.hairline]:
        page.rule(Rect(area.left, edge, area.width, s.hairline))
    for stone in layout.stones:
        top = flags_top + stone.row * line
        page.rule(Rect(stone.left - s.hairline, top, 2 * s.hairline, lanes_bottom - top),
                  weight="strong")

    for start, end, label in plan.phases:
        page.span(plot.over(span_band, start, end), label, size=size)
    for index, period in enumerate(plan.periods):
        page.period(plot.over(period_band, index, index + 1), period, size=size)

    for band, lane in zip(bands, packed):
        inner = band.inset(y=s.row_gap)
        page.lane(Rect(plot.names.left, inner.top, plot.names.width, inner.height), lane.name)
        tops = [inner.top]
        for tall in lane.heights:
            tops.append(tops[-1] + tall + extra + s.row_gap)
        for piece in lane.pieces:
            top, tall = tops[piece.row], lane.heights[piece.row] + extra
            if piece.point:
                page.diamond(Rect(piece.left, top + (tall - s.mark) // 2, s.mark, s.mark))
            else:
                page.bar(Rect(piece.left, top, piece.right - piece.left, tall),
                         piece.text if piece.side == "in" else "", piece.style_on(lane.tone), size=size)
            if piece.side == "right":
                page.label(Rect(piece.right + s.gap_s, top, piece.wide, tall), piece.text, size=size)
            elif piece.side == "left":
                page.label(Rect(piece.left - s.gap_s - piece.wide, top, piece.wide, tall),
                           piece.text, align="right", size=size)

    # またがる棒は区切りの線の上に置く (= 覆うレーンの間の線を棒が隠し、1 本に見える)
    for number, reach, piece in layout.across:
        top, bottom = plot.reaches(packed, number, number + reach - 1, extra, lanes_top)
        page.bar(Rect(piece.left, top, piece.right - piece.left, bottom - top), piece.text,
                 piece.style_on(packed[number].tone), size=size)

    for stone in layout.stones:
        top = flags_top + stone.row * line
        if stone.side == "right":
            page.label(Rect(stone.left + s.bar_pad_x, top, stone.wide, line), stone.text,
                       role="accent", size=size)
        else:
            page.label(Rect(stone.left - s.bar_pad_x - stone.wide, top, stone.wide, line),
                       stone.text, align="right", role="accent", size=size)


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
    plan = _read(spec)
    plot = _Plot(page.theme, area, plan)
    # 大きい文字から試し、頁に収まる最初の大きさで組む (= 余った高さは文字に配る)
    for size in page.theme.type.plan:
        try:
            layout = _measure(plot, plan, size)
            break
        except PageFullError as full:
            refused = full
    else:
        raise refused
    page.drew_a_diagram()  # レーンと棒で組んだ線表そのものが、この頁の図解
    _place(page, plot, plan, layout)
