"""One table of sizes, colours and type. Pages reference it; they never pick their own.

**デザインが毎回変わるのは、頁が自分で寸法と色を決めるから。**同じ役割の頁を
別の週に書くと、書いた人 (や私) の気分で 2 pt ずれ、灰色が 3 種類に増える。
ここを 1 枚に閉じ込め、頁からは名前でしか触れないようにする。

An entire deck's look is this file. Change a token, every page moves together.

A project may set three things for its own through `theme_from` at the bottom: the
typeface, the palette, and how large the type is — by saying what the deck is for
(`use`), and, role by role, with a size of its own. Margins and spacing stay here: a
project that can move its own margins is a project whose pages change shape from one
round to the next.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields, replace
from typing import ClassVar

from .geometry import Rect, cm, pt

SLIDE_16_9 = Rect(0, 0, 12192000, 6858000)

#: 1 文字が横に取る幅 (= 級数に対する比)。**字によって 3 倍違う**ので、一律の比で数えると
#: `i` の多い語は余り、`m` の多い語は溢れる。値は書体の file が持つ送り幅を測ったもので
#: (= `scripts/generate/measure-advance.py` が出す。0.02 刻みで切り上げ)、書体の系統ごとに 1 枚持つ。
#: `any` は測っていない書体が引く表で、幅の広い書体 (= Verdana / Meiryo) に合わせてある ―
#: 知らない書体では溢れない側へ外し、狭い書体では少し余る。全角は 1。
_ADVANCE = {
    "any": {
        0.28: "'il",
        0.36: " fj",
        0.38: ",.",
        0.40: "!t",
        0.44: "Ir",
        0.46: "\"()-/:;J[]|",
        0.54: "csz",
        0.56: "?L",
        0.58: "F",
        0.60: "ekvxy",
        0.62: "Pao",
        0.64: "$*0123456789ETY\\_`bdghnpqu{}",
        0.70: "ABCKRSVXZ",
        0.74: "&U",
        0.76: "HN",
        0.78: "DG",
        0.80: "OQ",
        0.82: "#+<=>^~",
        0.84: "w",
        0.86: "M",
        0.98: "m",
        1.02: "@W",
        1.08: "%",
    },
    "arial": {
        0.20: "'",
        0.24: "ijl",
        0.26: "|",
        0.28: " !,./:;I[\\]ft",
        0.34: "()-`r{}",
        0.36: "\"",
        0.40: "*",
        0.48: "^",
        0.50: "Jcksvxyz",
        0.56: "#$0123456789?L_abdeghnopqu",
        0.60: "+<=>~",
        0.62: "FTZ",
        0.68: "&ABEKPSVXY",
        0.74: "CDHNRUw",
        0.78: "GOQ",
        0.84: "Mm",
        0.90: "%",
        0.96: "W",
        1.02: "@",
    },
}
_ADVANCE_OF = {group: {character: wide for wide, characters in table.items() for character in characters}
               for group, table in _ADVANCE.items()}
#: 表のセルの状態の印 (= ○◔◑◕● と ✓△×) を置く書体。**印の字形を全部持つ書体は限られる** ―
#: 書体の file を読んで確かめたところ、Meiryo は 8 つとも持ち、Arial・Calibri・游ゴシックは 4 分の 1 と
#: 4 分の 3 の円、✓ を持たない。案件の書体が何であっても、印だけはこの書体で置く (= 字のまま置けるので、
#: 人が PowerPoint で直せる)
MARK_FACE = "Meiryo"
#: どの書体がどの表を引くか (= 名前の頭で引く)。Helvetica は Arial と同じ字幅に作られている
_FAMILY = {"arial": "arial", "helvetica": "arial"}
#: 表に無い半角 (= アクセント付きの字など) はこの幅で数える
_ADVANCE_OTHER = 0.7
#: 太字は同じ字でもこれだけ広い (= 測った書体の、小文字の平均)
_BOLD = {"any": 1.14, "arial": 1.10}


def advance(character: str, bold: bool = False, family: str = "") -> float:
    """How far one character moves the line along, as a fraction of the type size."""
    if ord(character) > 0x2E7F:
        return 1.0
    name = family.strip().lower()
    group = next((table for head, table in _FAMILY.items() if name.startswith(head)), "any")
    return _ADVANCE_OF[group].get(character, _ADVANCE_OTHER) * (_BOLD[group] if bold else 1)


@dataclass(frozen=True)
class Type:
    """Type sizes in points. `minimum` is the floor anything printed must clear."""

    title: float = 24
    heading: float = 16
    #: 流れ図の段の名前・線表のレーンの名前と、段の間の向き
    stage: float = 14
    marker: float = 28
    body: float = 12
    #: 出所と脚注、絵の下の説明だけ。頁の中身 (= 箱の本文、線表の名前) には使わない ― 席から
    #: 読める下限で、実物のデッキでは「文字が小さい」と差し戻された
    caption: float = 10
    minimum: float = 10
    family: str = "Meiryo"

    @property
    def plan(self) -> tuple[float, ...]:
        """線表の文字 (= 棒・印・帯・期間・日付の名前) の大きさ、大きい順。

        **頁に収まる最初の大きさ**を採る ― 余った高さは文字にも配り、詰まった頁は本文の大きさで
        組む。これより小さくはしない。段の名前の大きさと本文の大きさの 2 つから出るので、どちらかを
        案件が変えれば線表も付いて行く。
        """
        return tuple(sorted({self.stage, self.body}, reverse=True))


#: 資料の使い方ごとの文字の大きさ。`read` は手元で読ませる資料 (= 既定)、`present` は映して話す
#: 資料 ― 離れた席から読むので全部が 1.3〜1.5 倍で、載る量はそのぶん減る (= 要点だけを載せる)。
#: 案件は `[theme] use` でどちらかを選ぶ
USES = {
    "read": Type(),
    "present": Type(title=32, heading=24, stage=20, marker=36, body=18, caption=14, minimum=14),
}
#: 案件が 1 つずつ上書きできる大きさの役 (= `[theme.type]`)。向きの字と下限は使い方が決める
SIZED = ("title", "heading", "stage", "body", "caption")


#: 道具が持つ色の役 (= 頁の `tone` にいつでも書ける名前)。案件はこのほかに、意味の名前を付けた
#: 地を `[theme.grounds]` で宣言できる
ROLES = ("box", "band", "tint", "accent", "good", "bad")


def _luminance(colour: str) -> float:
    """How light a colour looks (= the relative luminance of WCAG 2)."""
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(int(colour[index:index + 2], 16)) for index in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(one: str, other: str) -> float:
    """How far apart two colours read (= the contrast ratio of WCAG 2, 1 to 21)."""
    light, dark = sorted((_luminance(one), _luminance(other)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


@dataclass(frozen=True)
class Palette:
    """Colours by meaning, not by name. `good`/`bad` mark a reading, never decoration."""

    ink: str = "1A1A1A"
    muted: str = "6B6B6B"
    accent: str = "1F5FA9"
    good: str = "1F5FA9"
    bad: str = "B3261E"
    band: str = "EAF0F8"
    box: str = "FFF4E5"
    #: 3 つめの薄い地 (= 同じ頁で 3 者を色で分けるとき)。⚠ テンプレートのテーマ色からは読まない ―
    #: 空いている枠には濃い色が入っていることが多く、薄い地のはずが文字の読めない色になる。
    #: 変えるのは案件の `[theme.palette]` だけ
    tint: str = "E8F3EA"
    #: 線表の列を 1 つおきに塗る、ごく薄い地 (= 棒の下に敷く。期間の境が一目で分かるように)。
    #: これも `[theme.palette]` でだけ変える
    wash: str = "F3F3F3"
    rule: str = "D9D9D9"
    paper: str = "FFFFFF"

    #: 薄い地 (= `box` / `band` / `tint`) の箱と棒が持つ枠の濃さ ― 地の色が白から離れているぶんを、
    #: この倍だけ離す。薄い地は列の地 (`wash`) とも紙とも近く、枠が無いと端が背景に溶ける
    #: (= 実物のデッキで「棒の境が分からない」と差し戻された)。色の役ではないので案件からは
    #: 変えられない ― 案件が地を変えれば、枠はその地から出し直される
    EDGE_DEPTH: ClassVar[float] = 6.0

    def words_on(self, ground: str) -> str:
        """The colour of words on a ground a project named: the ink or the paper, whichever reads better.

        ⚠ **閾値を置かない。**明るさの境目を数で決めると、境目の近くの色で読めない字が出る。
        本文の色と紙の色の両方を地と比べ、差の大きい方を採る。
        """
        return self.ink if contrast(ground, self.ink) >= contrast(ground, self.paper) else self.paper

    def edge(self, ground: str) -> str:
        """The colour of the line round a light ground: the same hue, further from white."""
        channels = (int(ground[index:index + 2], 16) for index in (0, 2, 4))
        return "".join(f"{max(round(255 - (255 - channel) * self.EDGE_DEPTH), 0):02X}"
                       for channel in channels)


@dataclass(frozen=True)
class Spacing:
    """The only distances a page may use."""

    margin_x: int = cm(1.2)
    margin_top: int = cm(0.9)
    margin_bottom: int = cm(0.9)
    gap_s: int = cm(0.3)
    gap_m: int = cm(0.6)
    gap_l: int = cm(1.0)
    pad: int = cm(0.35)
    #: 題の帯 (= 題の上の小さい字の段 + 題の段)。小さい字の在る頁も無い頁も、帯はこの高さ
    title_height: int = cm(1.5)
    #: そのうち、題の上の小さい字の段
    kicker_height: int = cm(0.5)
    cell_pad_y: int = cm(0.08)
    cell_pad_x: int = cm(0.18)
    #: 文字の枠が左右に自分で取る余白 (= pptx の既定)。文字が使える幅は、枠の幅からこの 2 つぶん狭い
    text_inset: int = cm(0.254)
    band_height: int = cm(1.1)
    footer_height: int = cm(0.7)
    #: 区切りの細い線 (= 題の下、線表の目盛り) と、箱と棒の枠
    hairline: int = pt(1)
    #: 線表の棒 ― 文字のまわりの余白、隣の棒との間、同じレーンの段と段の間
    bar_pad_x: int = cm(0.15)
    bar_pad_y: int = cm(0.12)
    bar_gap: int = cm(0.05)
    row_gap: int = cm(0.15)
    #: 時点の印 (= 菱形) の差し渡し
    mark: int = cm(0.4)
    #: 箱の左上に置くアイコンの一辺 (= 絵はこの正方形に縦横比を保って収める)
    icon: int = cm(1.2)
    #: 道のりの矢羽根の、尖った先 (と次の段の切り欠き) の深さ
    chevron_point: int = cm(0.6)
    #: 凡例の色見本の一辺
    swatch: int = cm(0.4)
    #: 強調した箱と棒の枠 (= クリティカルパス、目を集めたい 1 つ)。細い線の倍より太く
    strong_line: int = pt(2.25)


@dataclass(frozen=True)
class Theme:
    """Everything a page is allowed to know about how the deck looks."""

    slide: Rect = SLIDE_16_9
    type: Type = field(default_factory=Type)
    palette: Palette = field(default_factory=Palette)
    spacing: Spacing = field(default_factory=Spacing)
    #: 案件が意味の名前を付けた地 (= `[theme.grounds]`)。並びは宣言の順で、凡例もこの順に並ぶ
    grounds: tuple[tuple[str, str], ...] = ()

    def ground_names(self) -> tuple[str, ...]:
        return tuple(name for name, _colour in self.grounds)

    def frame(self) -> Rect:
        """The slide minus its margins — where every page starts."""
        s = self.spacing
        return self.slide.inset(left=s.margin_x, right=s.margin_x,
                                top=s.margin_top, bottom=s.margin_bottom)

    def line_height(self, size: float | None = None) -> int:
        """One line of type, including its leading."""
        return round(pt(self.type.body if size is None else size) * 1.45)

    def lines(self, text: str, width: int, size: float | None = None) -> int:
        """How many lines this text takes at that width.

        ⚠ **全角 1 文字ぶんの幅で数える** ― 日本語の頁なので、これが実寸に近く、
        英数字まじりでは多めに出る (= 余らせるほうへ外す)。折り返しを勘定せずに
        枠を割ると、見出しが本文に重なり、表の下の読み方が表の中へ入る
        (= どちらも実際に焼いて初めて出た)。
        """
        size = self.type.body if size is None else size
        per_line = max(int(width / pt(size)), 1)
        return max(sum(-(-len(line) // per_line) for line in str(text).split("\n")), 1)

    def text_height(self, text: str, width: int, size: float | None = None) -> int:
        """The height that text actually needs at that width."""
        return self.lines(text, width, size) * self.line_height(size)

    def width(self, text: str, size: float | None = None, *, bold: bool = False) -> int:
        """How wide this text runs on one line.

        `lines` は全角 1 文字ぶんで数えて余らせるが、**1 行に収まるかどうか**を決める場面では
        それだと欧文が倍に出て、収まる文字まで外へ追い出す。ここは字ごとの幅で数える
        (= `advance`)。半角を一律 0.6 文字ぶんで数えた間は、`m` を含む 4 文字の名前が枠から
        溢れて折れた (= 焼いて初めて出た)。
        """
        size = self.type.body if size is None else size
        family = self.type.family
        return round(max(sum(advance(c, bold, family) for c in line)
                         for line in str(text).split("\n")) * pt(size))

    def table_row_height(self) -> int:
        """One row: the line box plus the cell padding. Nothing renders shorter."""
        return self.line_height() + 2 * self.spacing.cell_pad_y

    def table_height(self, rows, widths: list[int] | None = None) -> int:
        """What a table will actually occupy.

        行数だけを渡すと 1 行 1 段として数える。中身と列幅を渡すと**折り返しを
        勘定する** ― 長いラベルの列は 2 段にも 3 段にもなる。
        """
        if isinstance(rows, int):
            return rows * self.table_row_height()
        if widths is None:
            return len(rows) * self.table_row_height()
        total = 0
        for row in rows:
            tallest = 1
            for cell, width in zip(row, widths):
                usable = width - 2 * self.spacing.cell_pad_x
                tallest = max(tallest, self.lines(cell, max(usable, 1)))
            total += tallest * self.line_height() + 2 * self.spacing.cell_pad_y
        return total

    def column_widths(self, rows, total: int) -> list[int]:
        """Share the width out by how much each column has to say.

        均等に割ると、長いラベルの列だけが折り返して表が縦に伸び、下に置いたはずの
        読み方を飲み込む。中身の最大の長さに比例させ、どの列にも下限を置く。
        """
        columns = max(len(row) for row in rows)
        want = [max((len(str(row[i])) if i < len(row) else 0) for row in rows) or 1
                for i in range(columns)]
        floor = total // (columns * 3)
        room = total - floor * columns
        scale = sum(want)
        widths = [floor + round(room * w / scale) for w in want]
        widths[-1] = total - sum(widths[:-1])
        return widths

    def wraps(self, text: str, width: int, size: float | None = None, *, bold: bool = False) -> int:
        """How many lines this text takes at that width, broken the way a text box breaks it.

        `lines` は全角 1 文字ぶんで数えて余らせる。地の文にはそれでよいが、**枠の高さを
        その字数で決める場所**では余りがそのまま空白になる ― 英数字と記号の短い見出しが
        2 行と数えられ、箱の中に 1 行ぶんの空きが残った。ここは語の切れ目で折る
        (= 空白で区切られた語は割らない、全角は 1 文字ごとに折れる)。幅は `width` と同じ数え方。

        ⚠ `width` は**文字が使える幅**で渡す (= 文字の枠は左右に `text_inset` を取る)。
        """
        size = self.type.body if size is None else size
        em, family = pt(size), self.type.family
        total = 0
        for paragraph in str(text).split("\n"):
            lines, used = 1, 0.0
            for space, word in re.findall(r"(\s*)([^\s\u2E80-\uFFFF]+|[\u2E80-\uFFFF])", paragraph):
                wide = sum(advance(c, bold, family) for c in word) * em
                lead = sum(advance(c, bold, family) for c in space) * em
                if used and used + lead + wide > width:
                    lines, used, lead = lines + 1, 0.0, 0.0
                if wide > width:                       # 1 語が 1 行より長い: 文字の途中で折れる
                    lines += int((used + wide) // width)
                    used = (used + wide) % width
                else:
                    used += lead + wide
            total += lines
        return max(total, 1)

    def unbreakable(self, text: str, size: float | None = None, *, bold: bool = False) -> int:
        """The width of the longest run that cannot be broken (= a word; a full-width character)."""
        size = self.type.body if size is None else size
        family = self.type.family
        runs = re.findall(r"[^\s\u2E80-\uFFFF]+|[\u2E80-\uFFFF]", str(text)) or [""]
        return round(max(sum(advance(c, bold, family) for c in run) for run in runs) * pt(size))

    def wrapped_height(self, text: str, width: int, size: float | None = None, *,
                       bold: bool = False) -> int:
        """The height that text needs at that width, by `wraps`."""
        return self.wraps(text, width, size, bold=bold) * self.line_height(size)

    def sticker_width(self, sticker: str) -> int:
        """How wide a page's sticker stands: its words on one line, with room at each side."""
        return self.width(sticker, self.type.body) + 2 * self.spacing.pad

    def title_lines(self, title: str, sticker: str = "") -> int:
        """How many lines a page's title breaks into, set across the frame beside its sticker.

        ⚠ **題の行を数えるのはここ 1 か所。**頁は題の帯の高さをこの数から取り、検査 (= `long_title`)
        は同じ数で 3 行以上を知らせる。別々に数えると、帯が 2 行ぶん取ったのに検査は 3 行と言う。
        札を持つ頁は、札と、札との間の空きのぶんだけ題が狭い。
        """
        room = self.frame().width - 2 * self.spacing.text_inset
        if sticker:
            room -= self.sticker_width(sticker) + self.spacing.gap_m
        return self.wraps(title, room, self.type.title, bold=True)

    def pt(self, size: float) -> int:
        """A type size in EMU, refusing anything below the floor."""
        if size < self.type.minimum:
            raise ValueError(f"{size}pt is below the {self.type.minimum}pt floor")
        return pt(size)


DEFAULT = Theme()


#: 色は 6 桁の 16 進で書く (= pptx がそう持つので、途中で変換しない)
_HEX = re.compile(r"\A[0-9A-Fa-f]{6}\Z")
#: 案件が自分で決めてよいもの。これ以外はツールが持つ
_MINE = ("font", "palette", "grounds", "use", "type")


class ThemeError(ValueError):
    """The project asked for a look that cannot be read."""


def theme_from(settings: dict | None) -> Theme:
    """The look a project sets for itself: its typeface, its colours, and how large its type is.

    ⚠ **余白と間隔は受け取らない。**案件ごとに余白が動くと、同じ役割の頁が週をまたいで別の形に
    なる (= 前の世代が壊れた道)。**見た目 (= どの書体で、どの色で、どの大きさで) は案件のもの、
    頁の割り方はツールのもの**という線をここで引く。

    文字の大きさは**資料の使い方**から決まる (= `use`。手元で読ませるか、映して話すか)。役ごとの
    上書き (= `[theme.type]`) も受け取るが、決める所は案件のこの 1 か所で、頁ごと・箱ごとには
    変えられない ― そこが動くと、同じ役の字が頁によって違う大きさになる。

    ⚠ **知らないキーは捨てずに拒む。**綴り違いを黙って落とすと、書いた人は見た目を変えた
    つもりで、焼いた頁は既定のまま出る。
    """
    if not settings:
        return DEFAULT

    _refuse_unknown(sorted(set(settings) - set(_MINE)), "theme", _MINE)

    family = str(settings.get("font", Type().family)).strip()
    if not family:
        raise ThemeError("theme.font is empty — name a typeface, or leave the key out")

    colours = settings.get("palette") or {}
    known = tuple(f.name for f in fields(Palette))
    _refuse_unknown(sorted(set(colours) - set(known)), "theme.palette", known)
    for name, value in colours.items():
        if not _HEX.match(str(value)):
            raise ThemeError(
                f"theme.palette.{name} is {value!r} — a colour is six hex digits "
                'with no "#", as in "1F5FA9"'
            )

    type = replace(_sizes(settings.get("use", "read"), settings.get("type")), family=family)
    return Theme(
        type=type,
        palette=Palette(**{name: str(value).upper() for name, value in colours.items()}),
        spacing=_furniture(type),
        grounds=_grounds(settings.get("grounds")),
    )


def _sizes(use, declared) -> Type:
    """The type sizes of a deck made for this use, with the project's own laid over them.

    ⚠ **下限より小さい大きさは拒む。**下限は使い方が決める (= 映す資料は、読ませる資料より高い)。
    小さくできる口が在ると、載り切らない頁は字を縮めて通され、席から読めない頁が戻ってくる。
    """
    if use not in USES:
        raise ThemeError(
            f"theme.use is {use!r} — a deck is made to be {' or '.join(repr(name) for name in USES)} "
            "(= read at a desk, or shown on a screen and spoken to)")
    declared = declared or {}
    if not isinstance(declared, dict):
        raise ThemeError("theme.type is a table of sizes in points, as in body = 14")
    _refuse_unknown(sorted(set(declared) - set(SIZED)), "theme.type", SIZED)
    floor = USES[use].minimum
    for name, value in declared.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ThemeError(f"theme.type.{name} is {value!r} — a size is a number of points, as in 14")
        if value < floor:
            raise ThemeError(
                f"theme.type.{name} is {value:g}pt, below the {floor:g}pt floor of a deck made to be "
                f"{use} — nothing smaller is readable there; say less on the page instead")
    return replace(USES[use], **declared)


def _furniture(type: Type) -> Spacing:
    """The spacing of a deck set in these sizes: the bands grow with the type that sits in them.

    題の帯・条件と結論の帯・出所の帯の高さは、そこに置く字の大きさに比例する (= 読ませる資料の
    大きさのとき、今までの高さ)。字だけ大きくして帯をそのままにすると、字が帯からはみ出す。
    余白と、物どうしの間隔は動かない。

    ⚠ **題の帯は 2 段で、段ごとに自分の字の大きさに比例する** (= 題の上の小さい字の段と、題の段)。
    帯を題の大きさだけで決めていた間は、小さい字だけを大きくした案件で、小さい字が題の頭に乗った。
    """
    base, read = Spacing(), USES["read"]
    kicker = round(base.kicker_height * type.caption / read.caption)
    return replace(
        base,
        kicker_height=kicker,
        title_height=kicker + round((base.title_height - base.kicker_height) * type.title / read.title),
        band_height=round(base.band_height * type.heading / read.heading),
        footer_height=round(base.footer_height * type.caption / read.caption),
    )


def _grounds(declared) -> tuple[tuple[str, str], ...]:
    """The grounds a project names for what they mean (= `[theme.grounds]`), in the order written.

    ⚠ **道具の色の役と同じ名前は拒む。**`box` を宣言で上書きできると、色の役を変える口が
    `[theme.palette]` と 2 つに割れる。
    """
    if not declared:
        return ()
    if not isinstance(declared, dict):
        raise ThemeError('theme.grounds is a table of names and colours, as in "内部向け" = "EAF0F8" '
                         '(= a name in Japanese is written in quotes)')
    found = []
    for name, value in declared.items():
        name = str(name).strip()
        if not name:
            raise ThemeError("theme.grounds has a ground with no name")
        if name in ROLES:
            raise ThemeError(
                f"theme.grounds.{name} is one of the palette's own roles ({', '.join(ROLES)}) — "
                "change its colour in [theme.palette], or give this ground a name of its own")
        if not _HEX.match(str(value)):
            raise ThemeError(
                f'theme.grounds.{name} is {value!r} — a colour is six hex digits with no "#", as in "EAF0F8"')
        found.append((name, str(value).upper()))
    return tuple(found)


def _refuse_unknown(unknown: list[str], where: str, known) -> None:
    if unknown:
        raise ThemeError(
            f"{where} does not take {', '.join(unknown)} (= it takes "
            f"{', '.join(sorted(known))}). A key nobody reads is a change that "
            "silently never happened."
        )
