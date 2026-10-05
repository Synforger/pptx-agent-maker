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
    """The sizes of one use: its type in points, and how tightly it sets what stands round the type.

    `minimum` is the floor anything printed must clear.
    """

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
    #: 余白と間隔の倍率 (= `read` の値の何倍か。物の内側と、物どうしの間に掛かる)
    tight: float = 1.0
    #: 余白と間隔のうち、1 つずつ決めた物 (= 名前と EMU。倍率より勝つ)。書けるのは案件の名前付きの使い方だけ
    spaced: tuple[tuple[str, int], ...] = ()

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
#: `sheet` は紙 1 枚で読ませる頁 (= 企画書の 1 枚、詳細を詰めた 1 枚) ― 手元で近くから読むので全部が
#: 0.75 倍で、余白と間隔も同じ比で詰まる。映す頁には使わない (= 席からは読めない)。
#: 案件は `[theme] use` でどれかを選び、自分の使い方を名前付きで足せる (= `[theme.uses]`)。
#: 資料 (= manifest) と頁は、その名前のどれかを `use` で名指して選ぶ
USES = {
    "read": Type(),
    "present": Type(title=32, heading=24, stage=20, marker=36, body=18, caption=14, minimum=14),
    "sheet": Type(title=18, heading=12, stage=10, marker=21, body=9, caption=8, minimum=8, tight=0.75),
}
#: 題の上の小さい字 (= 章の番号と名前) の置き場。`above` は題の上に小さく (= 既定)、`beside` は題の左に
#: 同じ行で、差し色の太字で置く。資料全体の見た目なので案件が `[theme] kicker` で決め、頁ごとには変えられない
KICKERS = ("above", "beside")
#: 案件が 1 つずつ上書きできる大きさの役 (= `[theme.type]`)。向きの字と下限は使い方が決める
SIZED = ("title", "heading", "stage", "body", "caption")
#: 使い方の倍率が掛かる余白と間隔 (= 物の内側と、物どうしの間、字に添える小さい物)。頁の縁の余白と
#: 線の太さには掛からない ― 縁は資料のどの頁でも同じ所に在り、線は細くすると消える
TIGHTENED = ("gap_s", "gap_m", "gap_l", "pad", "cell_pad_y", "cell_pad_x", "text_inset", "bar_pad_x", "bar_pad_y",
             "bar_gap", "row_gap", "mark", "icon", "chevron_point", "swatch")
#: 案件の名前付きの使い方が 1 つずつ決められる余白と間隔 (= `[theme.uses.<名前>.spacing]`、cm で書く)
SPACED = ("margin_x", "margin_top", "margin_bottom", "gap_s", "gap_m", "gap_l", "pad", "cell_pad_y", "cell_pad_x",
          "text_inset", "bar_pad_x", "bar_pad_y", "bar_gap", "row_gap")


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

    #: 表のセルの地の濃さの段 (= 差し色を紙の色へ、この数に割って薄める。`shade`)
    SHADES: ClassVar[int] = 4

    def shade(self, level: int) -> str:
        """The accent thinned toward the paper: `level` parts of `SHADES` are accent (= 0 is the paper)."""
        paper, accent = ([int(colour[index:index + 2], 16) for index in (0, 2, 4)]
                         for colour in (self.paper, self.accent))
        return "".join(f"{round(low + (high - low) * level / self.SHADES):02X}"
                       for low, high in zip(paper, accent))

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
class Under:
    """What the layout a declared page will sit on already has (= read from the specimen).

    型で組む頁は白紙に描いてから、テンプレートの 1 枚目のレイアウトへ向け直す。描く側が知るのは
    3 つだけ ― **題の枠が在るか** (= 在れば題はその枠として書かれ、色と書体をテンプレートから継ぐ)、
    **そこに何が印字されるか** (= ロゴや飾り。題の帯はその手前で止まる)、**頁に番号を振る資料か**
    (= 振る資料なら、型の頁もレイアウトの頁番号の枠を持つ)。余白と割り方は道具のまま。
    """

    title: bool = False
    #: レイアウトとマスターが印字する物の場所 (= 重なりの検査が「下敷き」と数える物と同じ)
    prints: tuple[Rect, ...] = ()
    #: レイアウトの頁番号の枠の名乗り (= `type` / `sz` / `idx` を、書かれている順のまま)。見本の頁が
    #: 1 枚も頁番号を持たない資料と、レイアウトに枠が無い資料では空 (= 型の頁も番号を持たない)
    number: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Theme:
    """Everything a page is allowed to know about how the deck looks."""

    slide: Rect = SLIDE_16_9
    type: Type = field(default_factory=Type)
    palette: Palette = field(default_factory=Palette)
    spacing: Spacing = field(default_factory=Spacing)
    #: 案件が意味の名前を付けた地 (= `[theme.grounds]`)。並びは宣言の順で、凡例もこの順に並ぶ
    grounds: tuple[tuple[str, str], ...] = ()
    #: 型の頁が乗るレイアウトが持つ物 (= 見本から読む。案件の `[theme]` からは書けない)
    under: Under = field(default_factory=Under)
    #: 題の上の小さい字の置き場 (= `KICKERS`。案件が `[theme] kicker` で決める)
    kicker: str = "above"
    #: この見た目の使い方の名前 (= 道具の `read` / `present` か、案件が `[theme.uses]` で名付けたもの)
    use: str = "read"
    #: この案件が知っている使い方と、それぞれの字の大きさ (= 資料と頁が `use` で名指す先。`using`)
    scales: tuple[tuple[str, Type], ...] = tuple(USES.items())

    def using(self, use: str | None) -> "Theme":
        """This look in the sizes of another use the project knows (= what a deck or a page names with `use`).

        変わるのは字の大きさと、それに付いて行く帯の高さだけ。書体・色・余白・下敷きは同じ資料のまま。

        ⚠ **選べるのは使い方の名前だけ** (= 大きさを 1 つずつは書けない)。役ごとの大きさが頁に書けると、同じ
        役の字が頁によって違う大きさになる。名前で選ぶなら、同じ使い方の頁どうしは必ず揃う。
        """
        if use is None or use == self.use:
            return self
        known = dict(self.scales)
        if not isinstance(use, str) or use not in known:
            raise ThemeError(
                f"`use` is {use!r} — this project knows {', '.join(repr(name) for name in known)} "
                "(= the toolkit's own, and the ones named under [theme.uses])")
        type = replace(known[use], family=self.type.family)
        return replace(self, use=use, type=type, spacing=_furniture(type))

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

    def clear(self, band: Rect) -> tuple[int, int]:
        """(left, right) of the stretch of a band that stays off what the layout prints there.

        帯に縦で掛かる物のうち、帯の右半分に在る物は右端を、左半分に在る物は左端を、その手前まで
        詰める。真ん中をまたぐ物 (= 頁を横切る飾り) は幅では避けられないので、そのまま ― 重なりの検査が
        言う。
        """
        left, right, gap = band.left, band.right, self.spacing.gap_s
        middle = band.left + band.width // 2
        for thing in self.under.prints:
            if (thing.bottom <= band.top or band.bottom <= thing.top
                    or thing.right <= band.left or band.right <= thing.left):
                continue
            if thing.left >= middle:
                right = min(right, thing.left - gap)
            elif thing.right <= middle:
                left = max(left, thing.right + gap)
        return left, right

    def kicker_lead(self, kicker: str) -> int:
        """How much of the title's line the small words take when they stand beside it (= none above it)."""
        if not kicker or self.kicker != "beside":
            return 0
        return self.spacing.text_inset + self.width(kicker, self.type.title, bold=True)

    def crossed(self, band: Rect) -> bool:
        """Whether the layout prints something across the middle of a band (= what `clear` cannot keep off).

        幅を詰めて避けられるのは、片側に在る物だけ。頁を横切る物 (= 罫線) に掛かるかどうかは、
        ここが言う。
        """
        middle = band.left + band.width // 2
        return any(thing.top < band.bottom and band.top < thing.bottom and thing.left < middle < thing.right
                   for thing in self.under.prints)

    def under_the_title(self, band: Rect) -> int:
        """Where the page may go on under its title band: under what the layout prints across the page there.

        ふつうは、帯の下端から中くらいの間隔を空けた所 (= 今までと同じ)。題の帯の下端より下、頁の上半分の
        うちに、レイアウトが頁を横切って印字する物 (= 題の下の罫線) が残っていて、そこから小さい間隔を空けた
        所の方が低ければ、そちら。帯の下の間隔に収まっている線は、何も動かさない。

        ⚠ **題の帯の高さは使い方で変わるが、レイアウトの線は動かない。**字の小さい使い方の頁 (= 紙 1 枚の頁) は
        帯が低く、本文がテンプレートの罫線より上から始まって、箱が罫線に乗った (= 検査は細い線を数えない)。

        頁の下半分に届く物 (= 出所の上の罫線、頁を丸ごと覆う地) は数えない ― その下から始めたら本文が無い。
        """
        middle = band.left + band.width // 2
        half = self.slide.top + self.slide.height // 2
        lowest = max((thing.bottom for thing in self.under.prints
                      if thing.left < middle < thing.right and band.bottom < thing.bottom <= half),
                     default=None)
        rest = band.bottom + self.spacing.gap_m
        return rest if lowest is None else max(rest, lowest + self.spacing.gap_s)

    def title_band(self, title: str, sticker: str = "", kicker: str = "") -> tuple[int, int, int]:
        """(lines, left, right) of a page's title band: how far the title folds, and where it may run.

        ⚠ **題の行を数えるのはここ 1 か所。**頁は題の帯の高さをこの数から取り、検査 (= `long_title`)
        は同じ数で 3 行以上を知らせる。別々に数えると、帯が 2 行ぶん取ったのに検査は 3 行と言う。
        札を持つ頁は、札と、札との間の空きのぶんだけ題が狭い。題の上の小さい字を題の左に置く資料
        (= `kicker = "beside"`) では、その字のぶんも狭い。

        ⚠ **帯は、レイアウトが印字する物の手前で止まる** (= `clear`)。頁の幅いっぱいに取っていた間は、
        右上のロゴに届いた題と、帯の右端に置く札が、重なりの検査で止まった。帯は題が折れるぶん下へ伸び、
        伸びた先に在る物も避けるので、行と幅は一緒に決める (= 避けて狭くなると、もう 1 行折れることがある)。
        """
        frame, s = self.frame(), self.spacing
        lines = 1
        while True:
            band = Rect(frame.left, frame.top, frame.width,
                        s.title_height + (lines - 1) * self.line_height(self.type.title))
            left, right = self.clear(band)
            room = right - left - 2 * s.text_inset
            if sticker:
                room -= self.sticker_width(sticker) + s.gap_m
            room -= self.kicker_lead(kicker)
            needed = self.wraps(title, max(room, 1), self.type.title, bold=True)
            if needed <= lines or band.bottom >= frame.bottom:
                return lines, left, right
            lines = needed

    def title_lines(self, title: str, sticker: str = "", kicker: str = "") -> int:
        """How many lines a page's title breaks into (= `title_band`)."""
        return self.title_band(title, sticker, kicker)[0]

    def pt(self, size: float) -> int:
        """A type size in EMU, refusing anything below the floor."""
        if size < self.type.minimum:
            raise ValueError(f"{size}pt is below the {self.type.minimum}pt floor")
        return pt(size)


DEFAULT = Theme()


#: 色は 6 桁の 16 進で書く (= pptx がそう持つので、途中で変換しない)
_HEX = re.compile(r"\A[0-9A-Fa-f]{6}\Z")
#: 案件が自分で決めてよいもの。これ以外はツールが持つ
_MINE = ("font", "palette", "grounds", "use", "type", "uses", "kicker")


class ThemeError(ValueError):
    """The project asked for a look that cannot be read."""


def theme_from(settings: dict | None) -> Theme:
    """The look a project sets for itself: its typeface, its colours, and how large its type is.

    ⚠ **余白と間隔を、頁や資料からは受け取らない。**頁ごとに余白が動くと、同じ役割の頁が週をまたいで
    別の形になる (= 前の世代が壊れた道)。**見た目 (= どの書体で、どの色で、どの大きさで) は案件のもの、
    頁の割り方はツールのもの**という線をここで引く。余白と間隔、字の下限を動かせるのは、案件が名前を
    付けた使い方の中だけ (= `[theme.uses]`。頁はその名前を選ぶので、同じ名前の頁は同じ形になる)。
    どう使うかは、道具が配る skill が縛る。

    文字の大きさは**資料の使い方**から決まる (= `use`。手元で読ませるか、映して話すか)。役ごとの
    上書き (= `[theme.type]`) と、案件が名前を付けた使い方 (= `[theme.uses]`) も受け取るが、大きさを
    決める所は案件のここだけ ― 資料と頁が選べるのは使い方の名前で (= `Theme.using`)、大きさそのものは
    書けない。そこが動くと、同じ役の字が頁によって違う大きさになる。

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

    kicker = settings.get("kicker", "above")
    if not isinstance(kicker, str) or kicker not in KICKERS:
        raise ThemeError(
            f"theme.kicker is {kicker!r} — the small words above a title stand "
            f"{' or '.join(repr(place) for place in KICKERS)} it")

    scales = {**USES, **_uses(settings.get("uses"))}
    use = settings.get("use", "read")
    if not isinstance(use, str) or use not in scales:
        raise ThemeError(
            f"theme.use is {use!r} — a deck is made to be {' or '.join(repr(name) for name in scales)} "
            "(= read at a desk, shown on a screen and spoken to, or a use named under [theme.uses])")
    # `[theme.type]` は、案件が選んだ使い方の大きさを上書きする (= ほかの使い方には掛からない)
    scales[use] = _sizes(f"a deck made to be {use}", scales[use], settings.get("type"), "theme.type")
    type = replace(scales[use], family=family)
    return Theme(
        use=use,
        scales=tuple(scales.items()),
        type=type,
        palette=Palette(**{name: str(value).upper() for name, value in colours.items()}),
        spacing=_furniture(type),
        grounds=_grounds(settings.get("grounds")),
        kicker=kicker,
    )


def _sizes(what: str, base: Type, declared, where: str, takes: tuple[str, ...] = SIZED) -> Type:
    """The sizes of one use, with what the project wrote for it laid over them.

    `what` は、誤りを言う時のその使い方の呼び方 (= `a deck made to be present`)、`where` は書かれた場所
    (= `theme.type`)。`takes` は、そこに書けるキー (= 誤りを言う時に並べる)。

    ⚠ **下限より小さい大きさは拒む。**下限は使い方が決める (= 映す資料は、読ませる資料より高い)。
    小さくできる口が在ると、載り切らない頁は字を縮めて通され、席から読めない頁が戻ってくる。
    下限そのものを動かせるのは、案件が名前を付けた使い方だけ (= `_uses` の `floor`)。
    """
    declared = declared or {}
    if not isinstance(declared, dict):
        raise ThemeError(f"{where} is a table of sizes in points, as in body = 14")
    _refuse_unknown(sorted(set(declared) - set(SIZED)), where, takes)
    for name, value in declared.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ThemeError(f"{where}.{name} is {value!r} — a size is a number of points, as in 14")
    sized = replace(base, **declared)
    for name in SIZED:
        value = getattr(sized, name)
        if value < sized.minimum:
            said = f"{where}.{name} is" if name in declared else f"{where} leaves {name} at"
            raise ThemeError(
                f"{said} {value:g}pt, below the {sized.minimum:g}pt floor of {what} "
                "— nothing smaller is readable there; say less on the page instead")
    return sized


def _uses(declared) -> dict[str, Type]:
    """The uses a project names for itself (= `[theme.uses.<name>]`), each with its sizes.

    1 つの使い方は、道具の使い方のどれに倣うか (= `like`。必須) と、そこから変える物で書く ― 役の大きさ、
    字の下限 (= `floor`)、余白と間隔 (= `[theme.uses.<名前>.spacing]`)。書かなかった物は倣った先のまま。

    ⚠ **道具は幅を持たせ、使い方は道具が配る skill が縛る。**下限と余白を動かせる口は、ここ 1 か所 (= 名前を
    付けた使い方) にだけ在る ― 頁や資料は名前で選ぶだけなので、同じ名前の頁はどこでも同じ形になる。

    ⚠ **道具の使い方と同じ名前は拒む。**`read` や `present` をここで書き換えられると、その大きさを決める
    口が `[theme.type]` と 2 つに割れる。
    """
    declared = declared or {}
    if not isinstance(declared, dict):
        raise ThemeError('theme.uses is a table of uses, each named: [theme.uses.detail] with like = "read"')
    found: dict[str, Type] = {}
    for name, said in declared.items():
        where = f"theme.uses.{name}"
        if name in USES:
            raise ThemeError(
                f"{where} — {name!r} is the toolkit's own use; give the project's use another name "
                "(= its sizes for the project's own `use` are written under [theme.type])")
        if not isinstance(said, dict):
            raise ThemeError(f'{where} is a table: like = "read", then the sizes it changes, as in body = 11')
        like = said.get("like")
        if not isinstance(like, str) or like not in USES:
            raise ThemeError(
                f"{where}.like is {like!r} — a use of the project's own starts from "
                f"{' or '.join(repr(use) for use in USES)}")
        base = _spaced(_floored(USES[like], said.get("floor"), where), said.get("spacing"), f"{where}.spacing")
        sizes = {key: value for key, value in said.items() if key not in ("like", "floor", "spacing")}
        found[name] = _sizes(f"the use {name!r}", base, sizes, where, ("like", "floor", "spacing", *SIZED))
    return found


def _floored(base: Type, floor, where: str) -> Type:
    """A use with a floor of its own under its type (= `floor`, in points; unsaid, that of the use it is like)."""
    if floor is None:
        return base
    if isinstance(floor, bool) or not isinstance(floor, (int, float)) or floor <= 0:
        raise ThemeError(f"{where}.floor is {floor!r} — a floor is a size in points above zero, as in 8")
    return replace(base, minimum=floor)


def _spaced(base: Type, declared, where: str) -> Type:
    """A use with spacing of its own: everything scaled together (= `scale`), and distances set one by one in cm.

    `scale` は、手元で読ませる資料の余白と間隔の何倍か (= `TIGHTENED` に掛かる。`sheet` は 0.75)。1 つずつ書いた
    距離 (= `SPACED`) は、倍率より勝つ。
    """
    if declared is None:
        return base
    if not isinstance(declared, dict):
        raise ThemeError(f"{where} is a table: scale = 0.6, or distances in cm one by one, as in pad = 0.2")
    _refuse_unknown(sorted(set(declared) - {"scale", *SPACED}), where, ("scale", *SPACED))
    for name, value in declared.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ThemeError(f"{where}.{name} is {value!r} — a number, as in 0.2")
    scale = declared.get("scale", base.tight)
    if scale <= 0:
        raise ThemeError(f"{where}.scale is {scale:g} — how many times the spacing of a deck to be read, above zero")
    one_by_one = {name: value for name, value in declared.items() if name != "scale"}
    for name, value in one_by_one.items():
        if value < 0:
            raise ThemeError(f"{where}.{name} is {value:g}cm — a distance is zero or more")
    return replace(base, tight=scale, spaced=tuple((name, cm(value)) for name, value in one_by_one.items()))


def _furniture(type: Type) -> Spacing:
    """The spacing of a deck set in these sizes: the bands grow with the type that sits in them.

    題の帯・条件と結論の帯・出所の帯の高さは、そこに置く字の大きさに比例する (= 読ませる資料の
    大きさのとき、今までの高さ)。字だけ大きくして帯をそのままにすると、字が帯からはみ出す。

    余白と、物どうしの間隔は、使い方が持つ倍率で決まる (= `Type.tight`。読ませる資料と映す資料は 1 倍で、
    今までの値のまま。紙 1 枚で読ませる頁は字と同じ比で詰まる)。字だけ小さくして間隔をそのままにすると、
    どの箱も中身の倍の高さを取る。使い方が 1 つずつ決めた距離 (= `Type.spaced`) は、倍率より勝つ。

    ⚠ **題の帯は 2 段で、段ごとに自分の字の大きさに比例する** (= 題の上の小さい字の段と、題の段)。
    帯を題の大きさだけで決めていた間は、小さい字だけを大きくした案件で、小さい字が題の頭に乗った。
    """
    base, read = Spacing(), USES["read"]
    if type.tight != 1:
        base = replace(base, **{name: round(getattr(base, name) * type.tight) for name in TIGHTENED})
    base = replace(base, **dict(type.spaced))
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
