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
* `period` ― 期間の名前 (= 列の見出しの枠)
* `stripe` ― 列を 1 つおきに塗る薄い地
* `diamond` ― 時点の印
* `rule` ― 区切りの細い線
* `label` ― 棒や印の隣、列の頭に付く 1 行の名前
* `lane` ― レーンの名前
* `footer` ― 出所

⚠ **図解を 1 つも持たない頁は組めない** (= 表と文章だけの頁を人に見せない)。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from .geometry import Rect
from .tokens import DEFAULT, ROLES, Theme


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
    #: 枠の色。空なら枠を引かない
    outline: str = ""
    dashed: bool = False
    #: 太い枠 (= 強調)
    heavy: bool = False


@dataclass(frozen=True)
class Card:
    """What one box says: a heading, a body under it, the ground it sits on and an icon beside it.

    カードも、流れ図と道のりのノードも、この 1 つの形で書く (= 読み口も置き方も 1 つ)。
    """

    heading: str
    body: str = ""
    tone: str = "box"
    #: 絵の file と、その縦横比 (= 無ければ None)
    icon: tuple[Path, float] | None = None
    #: 点線の枠 (= 在れば / 内容未定)
    tentative: bool = False
    #: 太い枠 (= クリティカルパス、目を集めたい 1 つ)
    strong: bool = False


@dataclass(frozen=True)
class Look:
    """How a box, a bar or an arrowhead is painted: one answer for all three."""

    fill: str
    ink: str
    outline: str
    dashed: bool = False
    heavy: bool = False


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
    """A shape that carries its own words: one shape, so a person can drag it whole."""

    text: str
    size: float
    colour: str
    #: 塗りの色。空なら塗らない
    fill: str = ""
    #: 枠の色。空なら枠を引かない
    outline: str = ""
    dashed: bool = False
    align: str = "center"
    bold: bool = False
    #: 形 (= `SHAPES`)。矩形のほかは、道のりの段の矢羽根だけ
    shape: str = "rect"
    #: 太い枠 (= 強調)
    heavy: bool = False
    #: 文字の左に空ける幅 (= 名前の前に置いたアイコンのぶん)
    lead: int = 0


#: 文字を持つ図形の形。`home` は左が平らで右が尖る矢羽根 (= 道のりの最初の段)、`chevron` は
#: 左が切り欠かれて右が尖る矢羽根 (= 2 段目から)
SHAPES = ("rect", "home", "chevron")


@dataclass(frozen=True)
class Diamond(Element):
    """A point in time. `rect` is the square the diamond sits in."""

    colour: str


#: 箱と棒の地に使える色の役。`box` / `band` / `tint` は薄い地で意味を持たない (= 3 者までを
#: 色で分けられる)。`accent` は目を集めたい物、`good` / `bad` は**読み** (= 良い / 悪い) を
#: 示す物にだけ使う
TONES = ROLES
#: 薄い地。紙とも列の地とも近いので、地を濃くした色の枠を持つ (= `Palette.edge`)
LIGHT = TONES[:3]


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

    def ground(self, tone: str) -> tuple[str, str, str]:
        """(the fill, the colour of words on it, the colour of its edge) for a tone.

        Dark grounds take the paper's colour for their words and no edge; light grounds take
        an edge, or they melt into whatever lies behind them.
        """
        p = self.theme.palette
        if tone in LIGHT:
            fill = getattr(p, tone)
            return fill, p.ink, p.edge(fill)
        if tone in TONES:
            return {"accent": p.accent, "good": p.good, "bad": p.bad}[tone], p.paper, ""
        # 案件が意味の名前を付けた地: 字は読める方の色、本文の色の字が乗る薄い地は枠を持つ
        fill = dict(self.theme.grounds)[tone]
        words = p.words_on(fill)
        return fill, words, p.edge(fill) if words == p.ink else ""

    def _legend_layout(self, rect: Rect, names: list[str]):
        """Where each entry of a legend goes: (left, top, width) per name, wrapping to a new line."""
        s = self.theme.spacing
        line = self.theme.line_height(self.theme.type.body)
        x, y = rect.left, rect.top
        for name in names:
            wide = s.swatch + s.gap_s + self.theme.width(name, self.theme.type.body)
            if x > rect.left and x + wide > rect.right:
                x, y = rect.left, y + line
            yield name, x, y, wide
            x += wide + s.gap_m

    def legend_height(self, width: int, names: list[str]) -> int:
        """How tall a legend of these names runs at this width."""
        line = self.theme.line_height(self.theme.type.body)
        tops = [top for _n, _x, top, _w in self._legend_layout(Rect(0, 0, width, line), names)]
        return max(tops) + line

    def look(self, tone: str, *, tentative: bool = False, strong: bool = False) -> Look:
        """How a box, a bar or an arrowhead is painted, from the attributes every one of them takes.

        `tentative` (= 点線) は地を紙の色にし、字と枠を灰色の点線にする ― 決まった物の隣で同じ重さに
        見えないように。`strong` (= 強調) は枠を本文の色の太い線にする (= 地の色を変えずに目を集める)。
        """
        p = self.theme.palette
        if tentative:
            fill, ink, outline = p.paper, p.muted, p.muted
        else:
            fill, ink, outline = self.ground(tone)
        if strong:
            outline = ink if tentative else p.ink
        return Look(fill, ink, outline, dashed=tentative, heavy=strong)

    def _lead_icon(self, rect: Rect, left: int, icon: tuple[Path, float] | None, size: float) -> int:
        """Put an icon in front of a name inside a bar or an arrowhead; how much room the words give it."""
        if not icon:
            return 0
        s = self.theme.spacing
        side = self.theme.line_height(size)
        source, aspect = icon
        square = Rect(left, rect.top + (rect.height - side) // 2, side, side)
        self.elements.append(Figure("icon", square.fit(aspect), Path(source), aspect))
        return side + s.gap_s

    def legend(self, rect: Rect, names: list[str]) -> None:
        """What each named ground means: a swatch and its name, left to right, in the order declared."""
        t, s, p = self.theme.type, self.theme.spacing, self.theme.palette
        line = self.theme.line_height(t.body)
        for name, x, y, wide in self._legend_layout(rect, names):
            fill, _words, edge = self.ground(name)
            self.elements.append(Fill("swatch", Rect(x, y + (line - s.swatch) // 2, s.swatch, s.swatch),
                                      fill, outline=edge))
            self.elements.append(Text("label", Rect(x + s.swatch + s.gap_s, y, wide - s.swatch - s.gap_s, line),
                                      name, t.body, p.ink))

    def boxes(self, rect: Rect, cards: list[Card], *, gap: int | None = None) -> None:
        """Cards side by side inside an area you already divided off.

        地の色は箱ごとの `tone` (= `TONES`)。薄い地の箱は枠を持つ (= `ground`)。アイコンの
        在る箱は、左上にアイコン、文字はその右に置く。

        ⚠ **見出しの高さは字数で決める。**比で割っていた間は、2 行に折り返した見出しが
        本文の上に乗った (= 焼いて初めて出た。枠の中に収まっているので検査は通る)。
        """
        t, s = self.theme.type, self.theme.spacing
        columns = rect.columns(len(cards), gap if gap is not None else s.gap_m)
        for card, said in zip(columns, cards):
            heading, body = said.heading, said.body
            look = self.look(said.tone, tentative=said.tentative, strong=said.strong)
            ink = look.ink
            self.elements.append(Fill("box", card, look.fill, outline=look.outline,
                                      dashed=look.dashed, heavy=look.heavy))
            inner = card.inset(s.pad)
            if said.icon:
                # ⚠ アイコンは頁の図解に数えない (= 図の要る頁が、アイコンだけで通らないように)
                source, aspect = said.icon
                square = Rect(inner.left, inner.top, s.icon, s.icon)
                self.elements.append(Figure("icon", square.fit(aspect), Path(source), aspect))
                inner = inner.inset(left=s.icon + s.gap_s)
            if body:
                needed = self.theme.wrapped_height(
                    heading, max(inner.width - 2 * s.text_inset, 1), t.heading, bold=True)
                head, rest = inner.split_top(
                    min(needed, max(inner.height - s.gap_s, 1)), gap=s.gap_s)
                self.elements.append(Text("box_body", rest, body, t.body, ink))
            else:
                head = inner
            self.elements.append(Text("box_heading", head, heading, t.heading, ink, bold=True))

    def figure(self, rect: Rect, source: Path | str, aspect: float, *, caption: str = "") -> None:
        """An image, kept at its own aspect ratio inside the area given.

        ⚠ **名は絵の下辺に付ける。**枠の下に固定していた間は、縦横比で縮んだぶんだけ
        絵と名が離れ、どの絵の名なのか読めなくなった。

        ⚠ **名のために取るのは、名が折れる行ぶんだけ。**枠の高さの 7 分の 1 を取って真ん中に
        置いていた間は、縦に長い枠ほど名が絵から離れて浮いた (= 段とマスで組んだ頁で焼いて出た)。
        """
        t, p, s = self.theme.type, self.theme.palette, self.theme.spacing
        area, tall = rect, 0
        if caption:
            tall = self.theme.wrapped_height(caption, max(rect.width - 2 * s.text_inset, 1), t.caption)
            area, _rest = rect.split_top(max(rect.height - tall - s.gap_s, 1))
        placed = area.fit(aspect)
        self.elements.append(Figure("figure", placed, Path(source), aspect))
        self._figures += 1
        if caption:
            strip = Rect(rect.left, placed.bottom + s.gap_s, rect.width, tall)
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

    def text(self, rect: Rect, text: str) -> None:
        """Words that are part of what the page says: the body's colour, at the body's size."""
        t, p = self.theme.type, self.theme.palette
        self.elements.append(Text("text", rect, text, t.body, p.ink))

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
        言い出した実例があるので、向きは文字で置く。小さい灰色の字のままだと頁の上で
        見えないので、本文と同じ濃さで大きく置く。
        """
        t, p = self.theme.type, self.theme.palette
        self.elements.append(Text("marker", rect, text, t.marker, p.ink, bold=True, align="center"))

    def stage(self, rect: Rect, name: str) -> None:
        """What one stage of a flow is called: the heading its nodes hang under."""
        t, p = self.theme.type, self.theme.palette
        self.elements.append(Text("stage", rect, name, t.stage, p.ink, bold=True, align="center"))

    def bar(self, rect: Rect, text: str, *, tone: str = "box", tentative: bool = False,
            size: float | None = None, strong: bool = False,
            icon: tuple[Path, float] | None = None) -> None:
        """Something that takes a stretch of time, with its name on it.

        `tone` は地の色の役 (= `TONES`。箱と同じ語彙)。薄い地の棒は、地を濃くした色の枠を持つ ―
        列の薄い地の上に置かれるので、枠が無いと端が背景に溶ける。
        `tentative` は**点線の枠** (= 在れば / 内容未定)。地は紙の色なので、決まった棒の
        隣に置いても同じ重さに見えない ― 塗らずに透かすと、後ろを通る日付の線が名前を貫く。

        ⚠ **文字は棒の中に持たせる** (= 別の枠にしない)。人が PowerPoint で棒を動かすとき、
        文字が置き去りにならない。アイコンは名前の前に、字の高さで置く。
        """
        size = self.theme.type.body if size is None else size
        look = self.look(tone, tentative=tentative, strong=strong)
        bar = Bar("bar", rect, text, size, look.ink, fill=look.fill, outline=look.outline,
                  dashed=look.dashed, heavy=look.heavy)
        self.elements.append(bar)
        lead = self._lead_icon(rect, rect.left + self.theme.spacing.bar_pad_x, icon, size)
        if lead:
            self.elements[self.elements.index(bar)] = replace(bar, lead=lead)

    def chevron(self, rect: Rect, text: str, *, shape: str, tone: str, size: float,
                tentative: bool = False, strong: bool = False,
                icon: tuple[Path, float] | None = None) -> None:
        """One stage of a road to a goal: an arrowhead with its name inside it.

        `shape` は `home` (= 最初の段、左が平ら) か `chevron` (= 2 段目から、左が切り欠き)。
        アイコンは名前の前に、切り欠きの内側から置く。
        """
        look = self.look(tone, tentative=tentative, strong=strong)
        head = Bar("chevron", rect, text, size, look.ink, fill=look.fill, outline=look.outline,
                   dashed=look.dashed, heavy=look.heavy, bold=True, shape=shape)
        self.elements.append(head)
        notch = self.theme.spacing.chevron_point if shape == "chevron" else 0
        lead = self._lead_icon(rect, rect.left + notch + self.theme.spacing.bar_pad_x, icon, size)
        if lead:
            self.elements[self.elements.index(head)] = replace(head, lead=lead)

    def span(self, rect: Rect, text: str, *, size: float | None = None) -> None:
        """What a stretch of periods is like (= movable, fixed), laid over the columns."""
        p = self.theme.palette
        size = self.theme.type.body if size is None else size
        self.elements.append(Bar("span", rect, text, size, p.ink, fill=p.rule))

    def period(self, rect: Rect, name: str, *, size: float | None = None) -> None:
        """What one column of a timeline is called, in a cell of its own (= a table's heading row)."""
        p = self.theme.palette
        size = self.theme.type.body if size is None else size
        self.elements.append(Bar("period", rect, name, size, p.paper, fill=p.accent, bold=True))

    def stripe(self, rect: Rect) -> None:
        """The faint ground under every other column, so the eye can follow a period down the page."""
        self.elements.append(Fill("stripe", rect, self.theme.palette.wash))

    def diamond(self, rect: Rect) -> None:
        """A point in time, drawn in the square given."""
        self.elements.append(Diamond("diamond", rect, self.theme.palette.accent))

    def rule(self, rect: Rect, *, weight: str = "light") -> None:
        """A thin line. `light` divides lanes, `firm` marks where one period ends and the next
        begins, `strong` is a date that cuts across the page."""
        p = self.theme.palette
        kind, colour = {"light": ("rule", p.rule), "firm": ("edge", p.muted),
                        "strong": ("line", p.accent)}[weight]
        self.elements.append(Fill(kind, rect, colour))

    def label(self, rect: Rect, text: str, *, align: str = "left", role: str = "ink",
              size: float | None = None) -> None:
        """A short name on one line: beside a bar or a mark, or at the head of a column.

        `role` は色の役 (= `ink` / `muted` / `accent`)。`accent` は頁を横切る日付の名前で、太字。

        ⚠ **折り返さない。**隣の物に付く名前なので、長すぎれば横へ伸びる ― 2 行に折ると
        下の段に乗る。
        """
        p = self.theme.palette
        size = self.theme.type.body if size is None else size
        colour = {"ink": p.ink, "muted": p.muted, "accent": p.accent}[role]
        self.elements.append(Text("label", rect, text, size, colour,
                                  bold=role == "accent", align=align))

    def lane(self, rect: Rect, name: str) -> None:
        """What one lane of a timeline is (= who, or which line of work)."""
        t, p = self.theme.type, self.theme.palette
        self.elements.append(Text("lane", rect, name, t.stage, p.ink, bold=True))

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
