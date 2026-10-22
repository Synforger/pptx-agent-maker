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
#: 等幅の書体は、半角が全部同じ幅 (= Consolas は 1 em の 1126/2048。PowerPoint の Mac 版に入っている 4 書体の
#: 字幅の表を読んで確かめた。太字も同じ幅)
_ADVANCE_OF["mono"] = {chr(code): 1126 / 2048 for code in range(0x20, 0x7F)}
#: 表のセルの状態の印 (= ○◔◑◕● と ✓△×) を置く書体。**印の字形を全部持つ書体は限られる** ―
#: 書体の file を読んで確かめたところ、Meiryo は 8 つとも持ち、Arial・Calibri・游ゴシックは 4 分の 1 と
#: 4 分の 3 の円、✓ を持たない。案件の書体が何であっても、印だけはこの書体で置く (= 字のまま置けるので、
#: 人が PowerPoint で直せる)
MARK_FACE = "Meiryo"
#: コード・コマンド・数式の行を置く等幅の書体 (= `compose` の文章の `role = "mono"`)。Windows と、PowerPoint の
#: Mac 版 (= app の中の書体) の両方に在る。案件の書体が何であっても、等幅の行だけはこの書体で置く (= 桁が揃わないコードは読めない)
MONO_FACE = "Consolas"
#: どの書体がどの表を引くか (= 名前の頭で引く)。Helvetica は Arial と同じ字幅に作られている
_FAMILY = {"arial": "arial", "helvetica": "arial", "consolas": "mono"}
#: 表に無い半角 (= アクセント付きの字など) はこの幅で数える
_ADVANCE_OTHER = 0.7
#: 太字は同じ字でもこれだけ広い (= 測った書体の、小文字の平均)
_BOLD = {"any": 1.14, "arial": 1.10, "mono": 1.0}


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
    #: 案件が書いた `band` と `display` と `tag` (= 書かなければ None で、下の 3 つが他の役から出す)
    band_set: float | None = None
    display_set: float | None = None
    tag_set: float | None = None
    #: この使い方が選んだ本体の箱の高さ (= `BOX_HEIGHTS`)。書かなければ None で、資料の `[theme] box_height`
    #: に倣う。案件が読み込む時 (= `theme_from`) に、書かなかった使い方へ資料の値が入る
    box_height_set: str | None = None
    #: この使い方が選んだ表の見た目 (= `TABLE_LOOKS`)。`box_height_set` と同じ作りで、書かなければ資料の
    #: `[theme] table_look` に倣う
    table_look_set: str | None = None
    #: この使い方の行の高さ (= 字の大きさに対する倍率)。書いた時だけ、見積りと書き出しの行間の両方がこの値に
    #: なる (= 描かれる行間が書体に依らない)。書かなければ見積りは `LEADING`、行間は書体任せ (= 今まで)
    leading_set: float | None = None

    @property
    def band(self) -> float:
        """条件と結論の帯の字。**書かなければ見出し。**

        帯の字と、カードの見出しは別の役 ― 見出しを 10.5 に下げる頁でも、帯は 16 のまま置ける。帯の高さは
        この大きさから割る (= `_furniture`)。
        """
        return self.heading if self.band_set is None else self.band_set

    @property
    def display(self) -> float:
        """特大の字 (= 頁の主役の数字。`compose` の文章の `role = "display"`)。**書かなければ題の 2 倍。**

        人が 1 番に選んだ資料 (= 見本の集まり) では、頁の主役の数字は題のおよそ 2〜3 倍で置かれていた。
        書かなければ題から出すので、案件が題の大きさを変えれば付いて行き、使い方 (= `present` / `sheet`) の
        比も保つ。
        """
        return self.title * 2 if self.display_set is None else self.display_set

    @property
    def tag(self) -> float:
        """札 (= カードの `tag = true`) の字。**書かなければ見出し。**

        札は、カードの見出しより大きく置く頁がある (= 札は段の名前で、見出しより目立たせたい)。同じ
        `heading` の役のままでは、見出しを下げると札も下がるので、別の役に分ける。札の高さを数える側
        (= `card_text`) と、描く側 (= `Page.boxes`) が同じ値を読む。
        """
        return self.heading if self.tag_set is None else self.tag_set

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
#: 本体の箱の高さ。`text` は箱ごとに字の分の高さ (= 既定。頁の下が空くことがある)、`page` は本体が持つ高さを
#: 箱の数で分け合って使い切る (= 字の分を超えたぶんを、同じ列の箱が等しく受ける)、`middle` は箱の高さは
#: `text` と同じで、本体に置いた物の塊を本体の縦の中央に置く (= 余りが上と下に半分ずつ)。資料全体の見た目
#: なので案件が `[theme] box_height` で決め、使い方ごと (= `[theme.uses.<名前>]`) にも選べるが、頁ごとには
#: 変えられない
BOX_HEIGHTS = ("text", "page", "middle")
#: カードの見た目。`filled` は地を色で塗る (= 既定)、`outlined` は地をほぼ紙の色にして、色は枠と見出しの字が
#: 持つ (= 色の役が同じなら、枠と見出しの色も同じ)。案件が `[theme] card_look` で決める
CARD_LOOKS = ("filled", "outlined")
#: 条件の帯と結論の帯の見た目。`plain` は枠の無い帯 (= 既定)、`outlined` は枠と色を持つ (= 上は差し色、
#: 下は灰)。案件が `[theme] band_look` で決める
BAND_LOOKS = ("plain", "outlined")
#: 表の見た目。`accent` は見出しの行を差し色で塗り、本文を 1 行おきに薄く敷く (= 既定。罫線は引かない)、
#: `plain` は見出しの行を灰の地に本文の色の太字にして、本文は紙の色のまま、どのセルにも灰の罫線を引く。
#: 資料全体の見た目なので案件が `[theme] table_look` で決め、使い方ごと (= `[theme.uses.<名前>]`) にも選べる
#: (= 表ごと・頁ごとには選べない)
TABLE_LOOKS = ("accent", "plain")
#: 案件が 1 つずつ上書きできる大きさの役 (= `[theme.type]`)。向きの字と下限は使い方が決める
SIZED = ("title", "heading", "stage", "body", "caption")
#: そのほか、案件が書ける役 (= `[theme.type]`)。書かなければ他の役から出る (= `Type.band` と `Type.tag` は
#: 見出し、`Type.display` は題の 2 倍)。書いた値は `Type` の `<名前>_set` に入る
DERIVED = ("band", "display", "tag")
#: 行の高さの見積り (= 字の大きさに対する倍率)。案件が `leading` を書かなければ、これで数え、行間は書体に任せる
LEADING = 1.45
#: 案件が書ける `leading` の幅 (= 1 より詰めると行が重なり、2 を越えると行の間が段落の間に見える)
LEADINGS = (1.0, 2.0)
#: 使い方の倍率が掛かる余白と間隔 (= 物の内側と、物どうしの間、字に添える小さい物)。頁の縁の余白と
#: 線の太さには掛からない ― 縁は資料のどの頁でも同じ所に在り、線は細くすると消える
TIGHTENED = ("gap_s", "gap_m", "gap_l", "gap_x", "gap_y", "band_gap", "title_gap", "pad", "cell_pad_y", "cell_pad_x",
             "text_inset", "bar_pad_x", "bar_pad_y", "bar_gap", "row_gap", "mark", "icon", "figure_floor", "chevron_point", "swatch")
#: 案件の名前付きの使い方が 1 つずつ決められる余白と間隔 (= `[theme.uses.<名前>.spacing]`、cm で書く)。
#: 条件の帯 (= `band_height`) と結論の帯 (= `conclusion_height`) の高さは、書けば字に比例しない
SPACED = ("margin_x", "margin_top", "margin_bottom", "gap_s", "gap_m", "gap_l", "gap_x", "gap_y", "band_gap", "title_gap",
          "pad", "cell_pad_y", "cell_pad_x", "text_inset", "bar_pad_x", "bar_pad_y", "bar_gap",
          "row_gap", "band_height", "conclusion_height", "figure_floor")


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


#: 字と地の明暗差の下限 (= WCAG 2 の AA)。普通の字と、大きい字 (= 18pt 以上、太字なら 14pt 以上)。
#: 組む側 (= `Palette.words_on`) と焼いた後の検査 (= `contrast`) が同じ値を読む
READABLE, READABLE_LARGE = 4.5, 3.0
#: 大きい字の境 (= pt。太字はこの下の値から)。下限と同じく、組む側と検査が同じ値を読む
LARGE_SIZE, LARGE_BOLD = 18.0, 14.0


def reading_floor(points: float | None, bold: bool = False) -> float:
    """The contrast words of this size and weight must reach (= 4.5, or 3 for large words).

    `points` を書いていない字 (= `None`) は大きい側で数える ― 検査が「迷ったら言わない側へ」倒す向きと同じ。
    """
    large = points is None or points >= LARGE_SIZE or (bold and points >= LARGE_BOLD)
    return READABLE_LARGE if large else READABLE


#: 通してよい字の色と地の色の組を書く鍵 (= 案件の `[checks]` の中)
ALLOWED = "contrast_allowed"
_PAIR_COLOUR = re.compile(r"#?([0-9A-Fa-f]{6})")


def allowed_pairs(config: dict) -> tuple[tuple[str, str], ...]:
    """The pairs a project lets through: (the words' colour, the ground's colour), as 6 upper-case hex digits.

    `[checks] contrast_allowed` を読む所はここ 1 つ ― 焼いた後の検査 (= `contrast`) は、これで通す組を決め、
    組む側 (= `Palette.words_on`) は、同じ組なら字の色を寄せない。
    """
    entries = config.get(ALLOWED, [])
    if not isinstance(entries, list):
        entries = [entries]
    pairs = []
    for entry in entries:
        found = [_PAIR_COLOUR.fullmatch(entry.get(key, "")) if isinstance(entry, dict) and isinstance(entry.get(key), str)
                 else None for key in ("words", "ground")]
        if not all(found):
            raise ValueError(
                f"[checks] {ALLOWED}: each pair is {{ words = \"FFFFFF\", ground = \"2E9E5B\" }} "
                f"(= the colour of the words and of the ground they sit on, 6 hex digits each), not {entry!r}")
        pair = tuple(match.group(1).upper() for match in found)
        if pair not in pairs:
            pairs.append(pair)
    return tuple(pairs)


def _towards(colour: str, end: str, share: float) -> str:
    """`colour` moved `share` of the way to `end` (= 0 is `colour`, 1 is `end`)."""
    return "".join(f"{round(low + (high - low) * share):02X}"
                   for low, high in ((int(colour[i:i + 2], 16), int(end[i:i + 2], 16)) for i in (0, 2, 4)))


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
    #: 検査で通すと決めた字の色と地の色の組 (= `[checks] contrast_allowed`。`allowed_pairs`)。色の役ではなく、
    #: `[theme.palette]` からは書けない ― 資料を組む時に、検査と同じ設定から渡される
    allowed: tuple[tuple[str, str], ...] = ()

    #: 薄い地 (= `box` / `band` / `tint`) の箱と棒が持つ枠の濃さ ― 地の色が白から離れているぶんを、
    #: この倍だけ離す。薄い地は列の地 (`wash`) とも紙とも近く、枠が無いと端が背景に溶ける
    #: (= 実物のデッキで「棒の境が分からない」と差し戻された)。色の役ではないので案件からは
    #: 変えられない ― 案件が地を変えれば、枠はその地から出し直される
    EDGE_DEPTH: ClassVar[float] = 6.0

    def words_on(self, ground: str, points: float | None, bold: bool = False) -> str:
        """The colour of words on a ground a project named: the ink or the paper, whichever reads better.

        ⚠ **地の明るさの境目で選ばない。**境目を数で決めると、境目の近くの色で読めない字が出る。
        本文の色と紙の色の両方を地と比べ、差の大きい方を採る。

        ⚠ **どちらも下限に届かない地では、届くまで色を寄せる。**中ほどの濃さの差し色は、墨とも紙とも
        4.5 に届かず、検査 `contrast` が宣言で組んだ表で当たった。差の大きい方を、地から離れる向き
        (= 黒か白) へ、届く最小の量だけ寄せる。寄せ切っても届かなければ (= 紙が既に白)、もう一方を
        寄せる。届いている地の色は動かさない。

        ⚠ **下限は字の大きさと太さで選ぶ** (= `reading_floor`。検査と同じ決まり)。大きい字と太字は 3 で
        足りるので、3 に届く紙の色は暗い色へ変えない。`points` を書かない字は大きい側で数える。

        ⚠ **検査で通すと決めた組は、組む時も寄せない** (= `allowed`)。選んだ字の色とその地の組が通す組に在れば、
        その色のまま置く。向きが逆の組や、片方の色だけが同じ組は通さない (= 検査と同じ)。
        """
        floor = reading_floor(points, bold)
        ranked = sorted((self.ink, self.paper), key=lambda colour: contrast(ground, colour), reverse=True)
        if (ranked[0].upper(), ground.upper()) in self.allowed:
            return ranked[0]
        for colour in ranked:
            end = "000000" if _luminance(colour) <= _luminance(ground) else "FFFFFF"
            for step in range(self.STEPS + 1):
                moved = _towards(colour, end, step / self.STEPS)
                if contrast(ground, moved) >= floor:
                    return moved
        return ranked[0]

    #: 字の色を寄せる刻み (= 黒か白までをこの数に割る。1 刻みが 1 階調)
    STEPS: ClassVar[int] = 255

    #: 表のセルの地の濃さの段 (= 差し色を紙の色へ、この数に割って薄める。`shade`)
    SHADES: ClassVar[int] = 4

    def shade(self, level: int) -> str:
        """The accent thinned toward the paper: `level` parts of `SHADES` are accent (= 0 is the paper)."""
        return self.thinned(level / self.SHADES)

    #: 目次の今の章の地 (= 差し色のごく薄い色)。差し色をこの割合だけ紙に混ぜる
    FAINT: ClassVar[float] = 0.07
    #: 枠を色で描くカードの地 (= `card_look = "outlined"`) と、枠を持つ帯の地 (= `band_look = "outlined"`)。
    #: 色をこの割合だけ紙に混ぜる ― カードはほぼ白、帯はそれより一段濃い (= 案件の資料の見本の透け方)
    CARD_WASH: ClassVar[float] = 0.03
    BAND_WASH: ClassVar[float] = 0.12
    #: 案件が名前を付けた地を「色で何も言わない薄い地」と見る明るさの下限: 作り付けの薄い地
    #: (= `box` / `band` / `tint`) の一番暗い物の明るさに、この倍率を掛けた所 (= 薄い地の色を案件が
    #: 変えれば線も動く)。中くらいの明るさの鮮やかな色は、本文の色の字が読めても薄い地ではない
    PALE_SHARE: ClassVar[float] = 0.9

    def pale(self, colour: str) -> bool:
        """Whether a colour is as near the paper as the palette's own pale grounds (= says nothing by its colour)."""
        return _luminance(colour) >= min(_luminance(c) for c in (self.box, self.band, self.tint)) * self.PALE_SHARE

    def thinned(self, share: float, hue: str | None = None) -> str:
        """A colour mixed into the paper: `share` of it is the colour (= 0 is the paper, 1 the colour).

        色を言わなければ差し色 (= `hue` は、読みの色や灰のように、差し色でない色を薄めたい時)。
        """
        paper, colour = ([int(colour[index:index + 2], 16) for index in (0, 2, 4)]
                         for colour in (self.paper, self.accent if hue is None else hue))
        return "".join(f"{round(low + (high - low) * share):02X}" for low, high in zip(paper, colour))

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
    #: `compose` の、同じ段のマスとマスの間 (= `gap_x`) と、段と段の間 (= `gap_y`)。使い方が `gap_m` だけ書けば
    #: 両方がそれに従う (= 書かなければ `gap_m` と同じ)。横の間だけ広げ、縦は詰める頁のための口
    gap_x: int = cm(0.6)
    gap_y: int = cm(0.6)
    #: 題の帯・条件の帯・結論の帯・足元の帯と、本体のあいだ。使い方が `gap_m` だけ書けばそれに従う。
    #: 物どうしの間を詰めても、帯と本体の間は詰めない頁のための口
    band_gap: int = cm(0.6)
    #: 題の帯と、その下の物 (= 条件の帯か本体) のあいだ。書かなければ `band_gap` に従う。題と条件の帯の間は
    #: 広く、条件の帯と本体の間は詰める頁のための口
    title_gap: int = cm(0.6)
    pad: int = cm(0.35)
    #: 題の帯 (= 題の上の小さい字の段 + 題の段)。小さい字の在る頁も無い頁も、帯はこの高さ
    title_height: int = cm(1.5)
    #: そのうち、題の上の小さい字の段
    kicker_height: int = cm(0.5)
    cell_pad_y: int = cm(0.08)
    cell_pad_x: int = cm(0.18)
    #: 文字の枠が左右に自分で取る余白 (= pptx の既定)。文字が使える幅は、枠の幅からこの 2 つぶん狭い
    text_inset: int = cm(0.254)
    #: 条件の帯 (= 題の下) と結論の帯 (= 足元の上) の高さ。書かなければどちらも、帯の字から割った高さ
    band_height: int = cm(1.1)
    conclusion_height: int = cm(1.1)
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
    #: 高さで詰められた絵が、ここより低くなるなら止まる (= 書かなければアイコンの一辺)。小さくても読める線画を
    #: 置く頁の使い方でだけ下げる口
    figure_floor: int = cm(1.2)
    #: 道のりの矢羽根の、尖った先 (と次の段の切り欠き) の深さ
    chevron_point: int = cm(0.6)
    #: 凡例の色見本の一辺
    swatch: int = cm(0.4)
    #: 強調した箱と棒の枠 (= クリティカルパス、目を集めたい 1 つ)。細い線の倍より太く
    strong_line: int = pt(2.25)


@dataclass(frozen=True)
class Under:
    """What the layout a declared page will sit on already has (= read from the specimen).

    型で組む頁は白紙に描いてから、テンプレートのレイアウトへ向け直す (= どのレイアウトかは `layout`)。
    描く側が知るのは 3 つだけ ― **題の枠が在るか、在ればどこか** (= 在れば題はその枠として書かれ、色と
    書体をテンプレートから継ぎ、題の帯の上下はその枠に合わせる)、**そこに何が印字されるか** (= ロゴや飾り。
    題の帯はその手前で止まる)、**頁に番号を振る資料か** (= 振る資料なら、型の頁もレイアウトの頁番号の枠を
    持つ)。余白と左右の割り方は道具のまま。
    """

    title: bool = False
    #: レイアウトとマスターが印字する物の場所 (= 重なりの検査が「下敷き」と数える物と同じ)
    prints: tuple[Rect, ...] = ()
    #: レイアウトの頁番号の枠の名乗り (= `type` / `sz` / `idx` を、書かれている順のまま)。見本の頁が
    #: 1 枚も頁番号を持たない資料と、レイアウトに枠が無い資料では空 (= 型の頁も番号を持たない)
    number: tuple[tuple[str, str], ...] = ()
    #: 題の枠の場所 (= レイアウトのか、それが場所を書いていなければマスターの)。題の枠が無ければ None
    title_frame: Rect | None = None
    #: レイアウトとマスターが引く線の、名前と場所 (= `prints` にも入っている。題の字を横切る物を名指すのに使う)
    lines: tuple[tuple[str, Rect], ...] = ()
    #: 型の頁が乗るレイアウトの部品の名前 (= `ppt/slideLayouts/` の中。`deck/pages/slides.py` がここへ向け直す)
    layout: str = "slideLayout1.xml"


class Band(str):
    """The words of a row that divides a table: one cell across every column, and the tone it asked for.

    字のまま表を通るので (= 印と濃さのセルと同じ)、表を読む所も置く所も、行が 1 つのセルの行かどうかだけを
    `divides` で問う。`tone` は書かれたまま (= 空は書かれていない)。色の役か `[theme.grounds]` の名前かは、
    地を引ける所 (= `Page.table`) が確かめる。
    """

    tone: str

    def __new__(cls, words: str, tone: str = "") -> "Band":
        cell = super().__new__(cls, words)
        cell.tone = tone
        return cell


def divides(row) -> bool:
    """Whether a row of a table is a band across it (= its one cell is a `Band`), not cells in columns."""
    return len(row) == 1 and isinstance(row[0], Band)


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
    #: 本体の箱の高さ (= `BOX_HEIGHTS`)、カードの見た目 (= `CARD_LOOKS`)、帯の見た目 (= `BAND_LOOKS`)。
    #: どれも既定は今までの見た目で、案件が `[theme]` で選ぶ
    box_height: str = "text"
    card_look: str = "filled"
    band_look: str = "plain"
    #: 表の見た目 (= `TABLE_LOOKS`)。これも既定は今までの見た目
    table_look: str = "accent"
    #: この見た目の使い方の名前 (= 道具の `read` / `present` か、案件が `[theme.uses]` で名付けたもの)
    use: str = "read"
    #: この案件が知っている使い方と、それぞれの字の大きさ (= 資料と頁が `use` で名指す先。`using`)
    scales: tuple[tuple[str, Type], ...] = tuple(USES.items())

    def using(self, use: str | None) -> "Theme":
        """This look in the sizes of another use the project knows (= what a deck or a page names with `use`).

        変わるのは字の大きさと、それに付いて行く帯の高さ、使い方が選んだ箱の高さ (= `box_height`) と表の
        見た目 (= `table_look`) だけ。書体・色・余白・下敷きは同じ資料のまま。

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
        box_height = type.box_height_set or self.box_height
        table_look = type.table_look_set or self.table_look
        return replace(self, use=use, type=type, spacing=_furniture(type), box_height=box_height,
                       table_look=table_look)

    def ground_names(self) -> tuple[str, ...]:
        return tuple(name for name, _colour in self.grounds)

    def frame(self) -> Rect:
        """The slide minus its margins — where every page starts.

        下の余白は、頁の足元 (= `foot`) から取る。レイアウトが頁の下に何も印字しなければ、頁の下端から。
        """
        s = self.spacing
        return self.slide.inset(left=s.margin_x, right=s.margin_x,
                                top=s.margin_top, bottom=self.slide.bottom - self.foot() + s.margin_bottom)

    def foot(self) -> int:
        """Where the page ends for what is placed on it: the top of what the layout prints across its lower half.

        ふつうは頁の下端。頁の下半分に、レイアウトが頁を横切って印字する物 (= 頁番号と注記の上に引いた線、
        足元の帯) が在れば、そのうちいちばん上の物の上端 ― そこから下はレイアウトの物で、本文から見れば頁の縁。

        ⚠ **頁の下端から余白を取っていた間は、レイアウトの線を見ていなかった。**線が頁の下端から 0.9cm より
        下に在るテンプレートで、本文の下端 (= 目次のカードの列、出所の帯) が線の 0.2cm 手前まで下り、
        テンプレートから複製した頁が線の手前に残す余白が無かった (= 重なってはいないので、検査は言わない)。
        線がそれより上に在れば、本文は線を越えて下まで続いていた (= 検査は細い線を数えない)。

        頁の上半分から始まる物 (= 頁を丸ごと覆う地、題の下の罫線) と、頁の片側に在る物 (= 隅のロゴ) は数えない。
        """
        middle = self.slide.left + self.slide.width // 2
        half = self.slide.top + self.slide.height // 2
        return min((thing.top for thing in self.under.prints
                    if thing.left < middle < thing.right and half <= thing.top < self.slide.bottom),
                   default=self.slide.bottom)

    def line_height(self, size: float | None = None) -> int:
        """One line of type, including its leading."""
        return round(pt(self.type.body if size is None else size) * (self.type.leading_set or LEADING))

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

    def width(self, text: str, size: float | None = None, *, bold: bool = False, family: str = "") -> int:
        """How wide this text runs on one line.

        `lines` は全角 1 文字ぶんで数えて余らせるが、**1 行に収まるかどうか**を決める場面では
        それだと欧文が倍に出て、収まる文字まで外へ追い出す。ここは字ごとの幅で数える
        (= `advance`)。半角を一律 0.6 文字ぶんで数えた間は、`m` を含む 4 文字の名前が枠から
        溢れて折れた (= 焼いて初めて出た)。
        """
        size = self.type.body if size is None else size
        family = family or self.type.family
        return round(max(sum(advance(c, bold, family) for c in line)
                         for line in str(text).split("\n")) * pt(size))

    def table_row_height(self) -> int:
        """One row: the line box plus the cell padding. Nothing renders shorter."""
        return self.line_height() + 2 * self.spacing.cell_pad_y

    def table_height(self, rows, widths: list[int] | None = None) -> int:
        """What a table will actually occupy.

        行数だけを渡すと 1 行 1 段として数える。中身と列幅を渡すと**折り返しを
        勘定する** ― 長いラベルの列は 2 段にも 3 段にもなる。

        ⚠ **折り返しは描かれる幅で数える** (= `wraps`)。全角 1 字ぶんで数える `lines` では、1 行に収まる
        全角の名前の列が 2 段と数えられ、入る表が「入らない」で止まった。見出しの行と区切りの行は太字で数える。
        """
        if isinstance(rows, int):
            return rows * self.table_row_height()
        if widths is None:
            return len(rows) * self.table_row_height()
        total = 0
        for index, row in enumerate(rows):
            tallest = 1
            bold = index == 0 or divides(row)
            # 区切りの行は全部の列をまたぐ (= 1 列の幅で折ると、長い区切りが何段にも数えられる)
            for cell, width in zip(row, [sum(widths)] if divides(row) else widths):
                usable = width - 2 * self.spacing.cell_pad_x
                tallest = max(tallest, self.wraps(str(cell), max(usable, 1), bold=bold))
            total += tallest * self.line_height() + 2 * self.spacing.cell_pad_y
        return total

    def column_widths(self, rows, total: int) -> list[int]:
        """Share the width out by how much each column has to say.

        均等に割ると、長いラベルの列だけが折り返して表が縦に伸び、下に置いたはずの
        読み方を飲み込む。列ごとに、いちばん長いセルが 1 行で要る幅 (= 描かれる幅と、セルの左右の余白) を
        測る。全部の列が折れずに入るなら、まずその幅を配り、余りを同じ比で足す。入らない時は、どの列にも
        下限を置いて、残りをその比で分ける。

        ⚠ **要る幅は字の数でなく描かれる幅で測る** (= `width`)。字の数の比で配った間は、全角の名前の列が
        数字の列と同じ割合でしか広がらず、折れて表が倍の高さに数えられた。見出しの行は太字で測る。
        """
        heading = rows[0] if rows and not divides(rows[0]) else None
        rows = [row for row in rows if not divides(row)] or rows        # 区切りの行は列の幅を決めない
        columns = max(len(row) for row in rows)
        pad = 2 * self.spacing.cell_pad_x
        want = [max((self.width(str(row[i]), bold=row is heading) if i < len(row) else 0) for row in rows) + pad
                for i in range(columns)]
        scale = sum(want)
        if scale <= total:
            widths = [w + round((total - scale) * w / scale) for w in want]
        else:
            floor = total // (columns * 3)
            room = total - floor * columns
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

    def crossing_line(self, row: Rect) -> tuple[str, Rect] | None:
        """The first line the layout draws across the middle of a row of type (= its name and where it is), if any.

        ⚠ **数えるのは線だけ。**題の後ろに敷く地 (= 帯の色の矩形や絵) は題がその上に乗るように描かれていて、
        字を横切っても題は読める。線が字の真ん中を通ると、取り消し線に見える。
        """
        middle = row.left + row.width // 2
        return next(((name, line) for name, line in self.under.lines
                     if line.top < row.bottom and row.top < line.bottom and line.left < middle < line.right), None)

    def title_row(self) -> tuple[int, int]:
        """(top, height) of a page's title band while its title stays on one line.

        ふつうは、頁の内側の枠の上端から、決まった高さ (= 今までと同じ)。レイアウトに題の枠が在る時は、
        その枠の上端から、その枠の高さ ― 型の頁の題が、複製した頁の題と同じ高さに出る。ただし枠の中を
        頁を横切って通る線 (= 題の下の罫線) が在れば、帯はその線の手前で止まる (= 線は題の下に来る)。
        高さは、題の 1 行より低くはしない。
        """
        frame, s = self.frame(), self.spacing
        seat = self.under.title_frame if self.under.title else None
        if seat is None:
            return frame.top, s.title_height
        bottom, middle = seat.bottom, seat.left + seat.width // 2
        for _name, line in self.under.lines:
            if line.left < middle < line.right and seat.top < line.top < bottom:
                bottom = line.top
        return seat.top, max(bottom - seat.top, self.line_height(self.type.title))

    def under_the_title(self, band: Rect) -> int:
        """Where the page may go on under its title band: under what the layout prints across the page there.

        ふつうは、帯の下端から中くらいの間隔を空けた所 (= 今までと同じ)。題の帯の下端より下、頁の上半分の
        うちに、レイアウトが頁を横切って印字する物 (= 題の下の罫線) が残っていて、そこから小さい間隔を空けた
        所の方が低ければ、そちら。帯の下の間隔に収まっている線は、何も動かさない。

        ⚠ **題の帯の高さは使い方で変わるが、レイアウトの線は動かない。**字の小さい使い方の頁 (= 紙 1 枚の頁) は
        帯が低く、本文がテンプレートの罫線より上から始まって、箱が罫線に乗った (= 検査は細い線を数えない)。

        頁の下半分に届く物 (= 出所の上の罫線、頁を丸ごと覆う地) は数えない ― その下から始めたら本文が無い
        (= 出所の上の罫線は、本文の終わる所を決める。`foot`)。
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
        top, first = self.title_row()
        lines = 1
        while True:
            band = Rect(frame.left, top, frame.width, first + (lines - 1) * self.line_height(self.type.title))
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
_MINE = ("font", "palette", "grounds", "use", "type", "uses", "kicker", "box_height", "card_look", "band_look", "leading",
         "table_look", "layout_of_page")


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
    known = tuple(f.name for f in fields(Palette) if f.name != "allowed")
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
    box_height = _choice(settings, "box_height", BOX_HEIGHTS, "the height of a page's boxes")
    card_look = _choice(settings, "card_look", CARD_LOOKS, "the look of a card")
    band_look = _choice(settings, "band_look", BAND_LOOKS, "the look of the bands over and under a page")
    table_look = _choice(settings, "table_look", TABLE_LOOKS, "the look of a table")
    # 型の頁を乗せるレイアウトは、見本を読む所が使う (= `deck/base/under.py`)。ここは書き方だけ確かめる
    on = settings.get("layout_of_page")
    if on is not None and (isinstance(on, bool) or not isinstance(on, int) or on < 1):
        raise ThemeError(
            f"theme.layout_of_page is {on!r} — it is the number of a specimen page (= 1, 2, ...), and the "
            "declared pages sit on the layout that page sits on")

    # 使い方が自分の箱の高さと表の見た目を書いていなければ、資料の値に倣う (= 頁が名指した使い方のそれは、そこから読める)
    leading = _leading(settings, "theme")
    scales = {name: replace(sized, box_height_set=sized.box_height_set or box_height,
                            table_look_set=sized.table_look_set or table_look,
                            leading_set=sized.leading_set or leading)
              for name, sized in {**USES, **_uses(settings.get("uses"))}.items()}
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
        box_height=type.box_height_set,
        card_look=card_look,
        band_look=band_look,
        table_look=type.table_look_set,
    )


def _choice(settings: dict, key: str, options: tuple[str, ...], what: str) -> str:
    """One of a few looks a project picks by name (= `[theme] <key>`); the first is the one left unsaid.

    ⚠ **知らない名前は拒む。**綴り違いを既定へ落とすと、書いた人は見た目を変えたつもりで、焼いた頁は
    今までのまま出る。
    """
    return _picked(settings, key, options, what, "theme") or options[0]


def _sizes(what: str, base: Type, declared, where: str, takes: tuple[str, ...] = (*SIZED, *DERIVED)) -> Type:
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
    _refuse_unknown(sorted(set(declared) - {*SIZED, *DERIVED}), where, takes)
    for name, value in declared.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ThemeError(f"{where}.{name} is {value!r} — a size is a number of points, as in 14")
    sized = replace(base, **{f"{name}_set" if name in DERIVED else name: value for name, value in declared.items()})
    for name in (*SIZED, *DERIVED):
        value = getattr(sized, name)
        if value < sized.minimum:
            said = f"{where}.{name} is" if name in declared else f"{where} leaves {name} at"
            raise ThemeError(
                f"{said} {value:g}pt, below the {sized.minimum:g}pt floor of {what} "
                "— nothing smaller is readable there; say less on the page instead")
    return sized


#: 使い方が大きさの役のほかに書けるキー (= 倣う先、下限、余白、資料の見た目のうち使い方ごとに選べる物)
_USE_KEYS = ("like", "floor", "spacing", "box_height", "table_look", "leading")


def _uses(declared) -> dict[str, Type]:
    """The uses a project names for itself (= `[theme.uses.<name>]`), each with its sizes.

    1 つの使い方は、道具の使い方のどれに倣うか (= `like`。必須) と、そこから変える物で書く ― 役の大きさ、
    字の下限 (= `floor`)、余白と間隔 (= `[theme.uses.<名前>.spacing]`)。書かなかった物は倣った先のまま。

    ⚠ **道具は幅を持たせ、使い方は道具が配る skill が縛る。**下限と余白を動かせる口は、ここ 1 か所 (= 名前を
    付けた使い方) にだけ在る ― 頁や資料は名前で選ぶだけなので、同じ名前の頁はどこでも同じ形になる。
    本体の箱の高さ (= `box_height`) と表の見た目 (= `table_look`) も同じ口で選べる (= 書かなければ資料の
    `[theme] box_height` と `[theme] table_look`)。

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
        base = replace(base,
                       box_height_set=_picked(said, "box_height", BOX_HEIGHTS, "the height of a page's boxes", where),
                       table_look_set=_picked(said, "table_look", TABLE_LOOKS, "the look of a table", where),
                       leading_set=_leading(said, where))
        sizes = {key: value for key, value in said.items() if key not in _USE_KEYS}
        found[name] = _sizes(f"the use {name!r}", base, sizes, where, (*_USE_KEYS, *SIZED, *DERIVED))
    return found


def _leading(said: dict, where: str) -> float | None:
    """The line height a deck or a use writes (= `leading`, a multiple of the type size); unsaid, None."""
    if "leading" not in said:
        return None
    value = said["leading"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not LEADINGS[0] <= value <= LEADINGS[1]:
        raise ThemeError(f"{where}.leading is {value!r} — the height of a line as a multiple of the type size, "
                         f"from {LEADINGS[0]} to {LEADINGS[1]} (= 1.2 is a single line of most typefaces)")
    return float(value)


def _picked(said: dict, key: str, options: tuple[str, ...], what: str, where: str) -> str | None:
    """A look picked by name (= `[theme] <key>`, or the same key of a use); unsaid, None.

    `what` は誤りを言う時のその見た目の呼び方、`where` は書かれた場所 (= `theme`、`theme.uses.<名前>`)。
    **書いてあるのに名前でない物 (= 空、数、真偽) は、書かなかった扱いにせず拒む。**
    """
    if key not in said:
        return None
    value = said[key]
    if not isinstance(value, str) or value not in options:
        raise ThemeError(f"{where}.{key} is {value!r} — {what} is {' or '.join(repr(name) for name in options)}")
    return value


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

    条件の帯 (= `band_height`) と結論の帯 (= `conclusion_height`) の高さは、使い方が書けば字に比例せず、書いた
    値のまま置く。結論の帯は、書かなければ条件の帯と同じ高さ。

    ⚠ **題の帯は 2 段で、段ごとに自分の字の大きさに比例する** (= 題の上の小さい字の段と、題の段)。
    帯を題の大きさだけで決めていた間は、小さい字だけを大きくした案件で、小さい字が題の頭に乗った。
    """
    base, read = Spacing(), USES["read"]
    if type.tight != 1:
        base = replace(base, **{name: round(getattr(base, name) * type.tight) for name in TIGHTENED})
    distances = dict(type.spaced)
    if "gap_m" in distances:
        # `gap_m` だけ書いた使い方では、段とマスの間も帯と本体の間も同じ距離のまま (= 今まで)。別に書けば別
        distances = {"gap_x": distances["gap_m"], "gap_y": distances["gap_m"], "band_gap": distances["gap_m"],
                     **distances}
    if "band_gap" in distances:
        # 題の下の間は、別に書かなければ帯と本体の間と同じ (= 今まで)
        distances = {"title_gap": distances["band_gap"], **distances}
    base = replace(base, **distances)
    kicker = round(base.kicker_height * type.caption / read.caption)
    said = dict(type.spaced)
    # 帯の高さは、書いた使い方では書いた値のまま ― 字に比例しない帯 (= 上と下で字の大きさが違う) を書くための口。
    # 結論の帯は、書かなければ上の帯と同じ高さ
    band = said["band_height"] if "band_height" in said else round(base.band_height * type.band / read.band)
    return replace(
        base,
        kicker_height=kicker,
        title_height=kicker + round((base.title_height - base.kicker_height) * type.title / read.title),
        band_height=band,
        conclusion_height=said.get("conclusion_height", band),
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
