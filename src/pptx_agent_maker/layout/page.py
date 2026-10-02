"""A page is declared by stacking and dividing, never by coordinates.

頁は上から順に「帯を置く」「残りを割る」だけで組む。**座標を書く口が無い**ので、
枠から出ることも、兄弟が重なることも起こらない ― 後から探す検査ではなく、
置き方の側で閉じている。

置ける物は意義を 1:1 で説明できる最小セットだけ:

* `title_bar` ― その頁が何の頁か
* `band` ― 条件の宣言 (= 上) と結論 (= 下)
* `box` ― 並ぶカード
* `figure` ― 実物の絵。縦横比は必ず保つ
* `table` ― 小さい表 (= 頁の主役にはしない)
* `note` ― 表や図の読み方 1〜2 行
* `points` ― 読み手に渡す要点の並び
* `caption` ― 置いた物の下に付く短い名
* `marker` ― 段と段の間の向き (= 文字で置く)
* `bar` ― 期間を占める棒 (= 文字を自分で持つ 1 つの図形)
* `span` ― 期間の性格を示す帯
* `diamond` ― 時点の印
* `rule` ― 区切りの細い線
* `label` ― 棒や印の隣、列の頭に付く 1 行の名前
* `lane` ― レーンの名前
* `footer` ― 出所

⚠ **図解を 1 つも持たない頁は組めない** (= 表と文章だけの頁を人に見せない)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .geometry import Rect
from .tokens import DEFAULT, Theme


@dataclass(frozen=True)
class Element:
    """Anything placed on the page. `rect` always came from dividing the frame."""

    kind: str
    rect: Rect


@dataclass(frozen=True)
class Text(Element):
    text: str
    size: float
    colour: str
    bold: bool = False
    align: str = "left"


@dataclass(frozen=True)
class Fill(Element):
    colour: str


@dataclass(frozen=True)
class Figure(Element):
    source: Path
    aspect: float


@dataclass(frozen=True)
class Table(Element):
    rows: tuple[tuple[str, ...], ...]
    header: bool = True
    highlight: dict[tuple[int, int], str] = field(default_factory=dict)
    #: 列ごとの幅 (= 中身の長さで配る。空なら均等)
    widths: tuple[int, ...] = ()


@dataclass(frozen=True)
class Bar(Element):
    """A rectangle that carries its own words: one shape, so a person can drag it whole."""

    text: str
    size: float
    colour: str
    #: 塗りの色。空なら塗らない
    fill: str = ""
    #: 枠の色。空なら枠を引かない
    outline: str = ""
    dashed: bool = False
    align: str = "center"


@dataclass(frozen=True)
class Diamond(Element):
    """A point in time. `rect` is the square the diamond sits in."""

    colour: str


class PageFullError(RuntimeError):
    """Raised when a page is asked for more room than it has left."""


class Page:
    """Build a page top-down. `body` is whatever space is still free."""

    def __init__(self, title: str, theme: Theme = DEFAULT, *, kicker: str = "",
                 condition: str = "", conclusion: str = "", footer: str = "",
                 needs_figure: bool = True) -> None:
        """Declare the whole frame at once: title, the bands, the footer.

        ⚠ **帯と出所はここで全部取る。** 後から下の帯を足せる形にしていた間は、
        先に受け取った `body` と重なった (= 実際に結論の帯が表の上に乗った)。
        `body` は残り全部で、それ以上は誰も削れない。
        """
        self.theme = theme
        self.elements: list[Element] = []
        self._remaining = theme.frame()
        self._figures = 0
        # 図解を持たなくてよいのは骨格の頁だけ (= 目次と、毎週積み上げる早見表)。
        # 決めるのは型で、宣言の側からは触れない ― 本文の頁がここを外せるなら、
        # 「表と文章だけ」の頁が戻ってくる。
        self._needs_figure = needs_figure
        self._title_bar(title, kicker)
        if condition:
            self._band(condition, conclusion=False)
        if footer:
            self._footer(footer)
        if conclusion:
            self._band(conclusion, conclusion=True)
        self._frozen = True

    # -- structure -----------------------------------------------------------

    @property
    def body(self) -> Rect:
        """The space not yet spoken for."""
        return self._remaining

    def _take_top(self, height: int) -> Rect:
        if getattr(self, "_frozen", False):
            raise RuntimeError("the frame is settled; everything else divides `body`")
        if height > self._remaining.height:
            raise PageFullError(
                f"asked for {height} EMU of height, {self._remaining.height} left — "
                "a page that does not fit is a page that needs splitting, not shrinking"
            )
        band, rest = self._remaining.rows([height, max(self._remaining.height - height, 1)])
        self._remaining = Rect(rest.left, band.bottom + self.theme.spacing.gap_m,
                               rest.width, self._remaining.bottom - band.bottom - self.theme.spacing.gap_m)
        return band

    def _take_bottom(self, height: int) -> Rect:
        if getattr(self, "_frozen", False):
            raise RuntimeError("the frame is settled; everything else divides `body`")
        if height > self._remaining.height:
            raise PageFullError(f"asked for {height} EMU of height, {self._remaining.height} left")
        top = Rect(self._remaining.left, self._remaining.top, self._remaining.width,
                   self._remaining.height - height - self.theme.spacing.gap_m)
        strip = Rect(self._remaining.left, self._remaining.bottom - height, self._remaining.width, height)
        self._remaining = top
        return strip

    # -- the things a page may contain ---------------------------------------

    def _title_bar(self, title: str, kicker: str) -> None:
        t, s, p = self.theme.type, self.theme.spacing, self.theme.palette
        bar = self._take_top(s.title_height)
        if kicker:
            kick, main = bar.rows([1, 2])
            self.elements.append(Text("kicker", kick, kicker, t.caption, p.muted))
        else:
            main = bar
        self.elements.append(Text("title", main, title, t.title, p.ink, bold=True))
        self.elements.append(Fill("rule", Rect(bar.left, bar.bottom, bar.width, s.hairline), p.rule))

    def _band(self, text: str, *, conclusion: bool = False) -> None:
        """A declared condition (top) or the reading to take away (bottom)."""
        p, t, s = self.theme.palette, self.theme.type, self.theme.spacing
        rect = self._take_bottom(s.band_height) if conclusion else self._take_top(s.band_height)
        self.elements.append(Fill("band", rect, p.rule if conclusion else p.band))
        self.elements.append(
            Text("band_text", rect.inset(s.pad), text, t.heading, p.ink, bold=conclusion)
        )

    def boxes(self, rect: Rect, cards: list[tuple[str, str]], *, gap: int | None = None,
              small: bool = False) -> None:
        """Cards side by side inside an area you already divided off.

        ⚠ **見出しの高さは字数で決める。**比で割っていた間は、2 行に折り返した見出しが
        本文の上に乗った (= 焼いて初めて出た。枠の中に収まっているので検査は通る)。
        """
        p, t, s = self.theme.palette, self.theme.type, self.theme.spacing
        columns = rect.columns(len(cards), gap if gap is not None else s.gap_m)
        for card, (heading, body) in zip(columns, cards):
            self.elements.append(Fill("box", card, p.box))
            inner = card.inset(s.pad)
            body_size = t.caption if small else t.body
            if body:
                needed = self.theme.text_height(heading, inner.width, t.heading)
                head, rest = inner.split_top(
                    min(needed, max(inner.height - s.gap_s, 1)), gap=s.gap_s)
                self.elements.append(Text("box_body", rest, body, body_size, p.ink))
            else:
                head = inner
            self.elements.append(Text("box_heading", head, heading, t.heading, p.ink, bold=True))

    def figure(self, rect: Rect, source: Path | str, aspect: float, *, caption: str = "") -> None:
        """An image, kept at its own aspect ratio inside the area given.

        ⚠ **名は絵の下辺に付ける。**枠の下に固定していた間は、縦横比で縮んだぶんだけ
        絵と名が離れ、どの絵の名なのか読めなくなった。
        """
        t, p, s = self.theme.type, self.theme.palette, self.theme.spacing
        area = rect
        if caption:
            area, _rest = rect.rows([6, 1], gap=s.gap_s)
        placed = area.fit(aspect)
        self.elements.append(Figure("figure", placed, Path(source), aspect))
        self._figures += 1
        if caption:
            strip = Rect(rect.left, placed.bottom + s.gap_s, rect.width,
                         max(rect.bottom - placed.bottom - s.gap_s, self.theme.line_height(t.caption)))
            self.elements.append(Text("caption", strip, caption, t.caption, p.muted, align="center"))

    def table(self, rect: Rect, rows: list[list[str]], *, header: bool = True,
              highlight: dict[tuple[int, int], str] | None = None) -> Rect:
        """A small table. Empty cells are refused: write a dash if there is no value.

        ⚠ **表の高さは行数が決める。**渡した枠は上限であって指示ではなく、行が
        入り切らなければ PowerPoint は枠を下へ伸ばす (= 頁から溢れる)。ここで
        必要な高さを測り、入らない宣言をその場で拒む。
        """
        widths = self.theme.column_widths(rows, rect.width)
        needed = self.theme.table_height(rows, widths)
        if needed > rect.height:
            raise ValueError(
                f"{len(rows)} rows need {needed} EMU but the area is {rect.height} — "
                "give the table more room, or fewer rows; it will not shrink"
            )
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                if str(cell).strip() == "":
                    raise ValueError(
                        f"empty cell at row {r}, column {c} — write an explicit dash; "
                        "a blank reads as a value nobody managed to fill in"
                    )
        placed = Rect(rect.left, rect.top, rect.width, needed)
        self.elements.append(
            Table("table", placed, tuple(tuple(str(c) for c in row) for row in rows),
                  header, highlight or {}, tuple(widths))
        )
        return placed

    def note(self, rect: Rect, text: str) -> None:
        """One or two lines telling the reader how to read what is above."""
        t, p = self.theme.type, self.theme.palette
        self.elements.append(Text("note", rect, text, t.body, p.muted))

    def points(self, rect: Rect, items: list[str]) -> None:
        """The readings this page hands over, one per line.

        `note` (= 図表の読み方) とは別物なので分けてある ― こちらは頁の中身そのもので、
        行が増えれば頁が持てる量を超える。空の行は落とす (= 文字の無い run を書かない)。
        """
        t, p = self.theme.type, self.theme.palette
        # 先頭の空白は階層なので残す (= 落とすと章と小項目が同じ並びに潰れる)
        lines = [f"{' ' * (len(str(item)) - len(str(item).lstrip()))}\u2014 {str(item).strip()}"
                 for item in items if str(item).strip()]
        if not lines:
            raise ValueError(
                "points was given nothing to say — drop the block rather than "
                "leaving an empty one"
            )
        self.elements.append(Text("points", rect, "\n".join(lines), t.body, p.ink))

    def caption(self, rect: Rect, text: str, *, align: str = "center") -> None:
        """A label under something the type has already placed."""
        t, p = self.theme.type, self.theme.palette
        self.elements.append(Text("caption", rect, text, t.caption, p.muted, align=align))

    def drew_a_diagram(self) -> None:
        """Declare that this page says something with shapes, not just words.

        図解は絵だけではない ― 工程の流れを図形で組んだ頁も図解を持っている。置いた
        側にしか分からないので、型がここで宣言する (= 宣言しない頁は、絵を 1 枚も
        持たないまま `build` に拒まれる)。
        """
        self._figures += 1

    def marker(self, rect: Rect, text: str) -> None:
        """A single character carrying direction (= the arrow between two stages).

        ⚠ **矢印は図形で描かない。**プリセットの矢印 1 つで PowerPoint が修復を
        言い出した実例があるので、向きは文字で置く。
        """
        t, p = self.theme.type, self.theme.palette
        self.elements.append(Text("marker", rect, text, t.heading, p.muted, align="center"))

    def bar(self, rect: Rect, text: str, *, tone: int = 0, tentative: bool = False) -> None:
        """Something that takes a stretch of time, with its name on it.

        `tone` はレーンごとに替える地の色 (= 隣のレーンと見分けるためで、意味は持たない)。
        `tentative` は**点線の枠** (= 在れば / 内容未定)。地は紙の色なので、決まった棒の
        隣に置いても同じ重さに見えない ― 塗らずに透かすと、後ろを通る日付の線が名前を貫く。

        ⚠ **文字は棒の中に持たせる** (= 別の枠にしない)。人が PowerPoint で棒を動かすとき、
        文字が置き去りにならない。
        """
        t, p = self.theme.type, self.theme.palette
        if tentative:
            self.elements.append(Bar("bar", rect, text, t.caption, p.muted,
                                     fill=p.paper, outline=p.muted, dashed=True))
        else:
            self.elements.append(Bar("bar", rect, text, t.caption, p.ink,
                                     fill=(p.box, p.band)[tone % 2]))

    def span(self, rect: Rect, text: str) -> None:
        """What a stretch of periods is like (= movable, fixed), laid over the columns."""
        t, p = self.theme.type, self.theme.palette
        self.elements.append(Bar("span", rect, text, t.caption, p.ink, fill=p.rule))

    def diamond(self, rect: Rect) -> None:
        """A point in time, drawn in the square given."""
        self.elements.append(Diamond("diamond", rect, self.theme.palette.accent))

    def rule(self, rect: Rect, *, strong: bool = False) -> None:
        """A thin line: a division between columns or lanes, or (`strong`) a date that cuts across them."""
        p = self.theme.palette
        self.elements.append(Fill("line" if strong else "rule", rect, p.accent if strong else p.rule))

    def label(self, rect: Rect, text: str, *, align: str = "left", role: str = "ink") -> None:
        """A short name on one line: beside a bar or a mark, or at the head of a column.

        `role` は色の役 (= `ink` / `muted` / `accent`)。`accent` は頁を横切る日付の名前で、太字。

        ⚠ **折り返さない。**隣の物に付く名前なので、長すぎれば横へ伸びる ― 2 行に折ると
        下の段に乗る。
        """
        t, p = self.theme.type, self.theme.palette
        colour = {"ink": p.ink, "muted": p.muted, "accent": p.accent}[role]
        self.elements.append(Text("label", rect, text, t.caption, colour,
                                  bold=role == "accent", align=align))

    def lane(self, rect: Rect, name: str) -> None:
        """What one lane of a timeline is (= who, or which line of work)."""
        t, p = self.theme.type, self.theme.palette
        self.elements.append(Text("lane", rect, name, t.caption, p.ink, bold=True))

    def _footer(self, text: str) -> None:
        """Where the numbers came from."""
        t, p, s = self.theme.type, self.theme.palette, self.theme.spacing
        rect = self._take_bottom(s.footer_height)
        self.elements.append(Text("footer", rect, text, t.caption, p.muted))

    # -- finishing -----------------------------------------------------------

    def build(self) -> list[Element]:
        """Hand over the placed elements, refusing a page with nothing to look at."""
        if self._needs_figure and self._figures == 0:
            raise ValueError(
                "this page has no figure — a page of prose and tables is the one thing "
                "the reader cannot use"
            )
        return list(self.elements)
