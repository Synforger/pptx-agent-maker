"""A page is declared by stacking and dividing, never by coordinates.

頁は上から順に「帯を置く」「残りを割る」だけで組む。**座標を書く口が無い**ので、
枠から出ることも、兄弟が重なることも起こらない ― 後から探す検査ではなく、
置き方の側で閉じている。

置ける物は意義を 1:1 で説明できる最小セットだけ:

* `title_bar` ― その頁が何の頁か (= 題と、その上か左に置く小さい字)
* `band` ― 条件の宣言 (= 上) と結論 (= 下)
* `box` ― 並ぶカード
* `panel` ― 他の箱を中に持つ箱 (= 見出しと線を左上に置く。中の割り方は呼ぶ側)
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
* `chart` ― 数字から描くグラフ (= 人が PowerPoint で数字を直せる)
* `footer` ― 出所
* `sticker` ― 頁の性格を言う札 (= 暫定・イメージ。題の帯の右端に 1 つ)

⚠ **図解を 1 つも持たない頁は組めない** (= 表と文章だけの頁を人に見せない)。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..geometry import Rect, cm
from ..tokens import DEFAULT, MONO_FACE, PAPER, Band, Theme, divides
from .elements import Bar, Chart, Diamond, Element, Ellipse, Figure, Fill, Lead, Line, Mark, Shade, Table, Text, TEXT_INSET_Y, bullet_indent
from .look import LIGHT, Look, Style, TONES


@dataclass(frozen=True)
class Voice:
    """What one person said, in their words, and who said it (= `who` may be left out)."""

    text: str
    who: str = ""
    #: 吹き出しの地の色の役 (= 箱と同じ語彙)
    style: Style = Style()


#: 吹き出し 1 つの幅の下限 (= 本文の大きさで 1 行に 10 字ほど)。マスの幅をこれで割った数が、1 行に並ぶ数
VOICE_WIDTH = cm(5.5)


@dataclass(frozen=True)
class Card:
    """What one box says: a heading, a body under it, the ground it sits on and an icon beside it.

    カードも、流れ図と道のりのノードも、この 1 つの形で書く (= 読み口も置き方も 1 つ)。
    """

    heading: str
    body: str = ""
    #: 地の色の役・アイコン・点線・強調 (= 棒や矢羽根と同じ 1 組)
    style: Style = Style()
    #: 札 (= 薄い灰の地に、色の役の色の枠と太字を 1 行・中央寄せで置く。見出しだけを持つ)
    tag: bool = False
    #: 字の寄せ (= `CARD_ALIGNS`)。札は常に中央
    align: str = "left"
    #: `body` の各行を「•」の行にする (= 本文は行ごとに改行で区切って持つ)
    bullets: bool = False


@dataclass(frozen=True)
class Panel:
    """A box that holds other boxes: a ground and an edge, and a heading in its top left corner.

    中身 (= 段とマス) は持たない。持つのは箱としての見た目だけで、中の割り方は `compose` が自分の段とマスの
    組み方をそのまま使う (= 別の並べ方を作らない)。
    """

    heading: str = ""
    #: 地の色の役・点線・強調 (= カードと同じ読み方。アイコンは持たない)
    style: Style = Style()
    #: 見出しの下の細い線 (= 見出しが在る時だけ)
    rule: bool = False


#: カードの字の寄せ
CARD_ALIGNS = ("left", "center")

def card_text(theme: Theme, card: Card, room: int) -> tuple[int, int]:
    """(the height of the heading, the height of the body) of a card, at this width for its words.

    カードの高さを数える側 (= `card_height`) と、置く側 (= `Page.boxes`) が同じ数を使う。見出しの無いカードは
    見出しの高さが 0、本文の無いカードは本文の高さが 0。札は 1 行で、折れるなら止まる。
    `room` は文字が使える幅 (= 文字の枠は左右に `text_inset` を取る)。
    """
    t = theme.type
    if card.tag:
        if theme.wraps(card.heading, room, t.tag, bold=True) > 1:
            raise PageFullError(
                f"the tag {card.heading!r} does not fit on one line of its box — a tag is a word or two "
                "(= a stage, a number), not a sentence")
        return theme.line_height(t.tag), 0
    head = theme.wrapped_height(card.heading, room, t.heading, bold=True) if card.heading else 0
    # 「•」の行は点の分だけ字が内に入る (= 折り返しもその幅で数える)
    width = max(room - bullet_indent(t.body), 1) if card.bullets else room
    return head, theme.wrapped_height(card.body, width, t.body) if card.body else 0


#: 凡例の点線の見本の長さ (= 色見本の一辺の倍数。1 つぶんでは破線が 2 本しか入らず、点線と読めない)
DOTTED_KEY = 2


def _entries(names: list[str], dotted: str, swatch: int) -> list[tuple[str, int]]:
    """What a legend lists, in order, each with the width of its key: the names of the grounds, then the words of the dotted line (= if it has any)."""
    return [(name, swatch) for name in names] + ([(dotted, swatch * DOTTED_KEY)] if dotted else [])


class PageFullError(RuntimeError):
    """Raised when a page is asked for more room than it has left."""


class Page:
    """Build a page top-down. `body` is whatever space is still free."""

    def __init__(self, title: str, theme: Theme = DEFAULT, *, kicker: str = "",
                 condition: str = "", conclusion: str = "", footer: str = "",
                 sticker: str = "", needs_figure: bool = True) -> None:
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
        self._title_bar(title, kicker, sticker)
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

    def _take_top(self, height: int, gap: int | None = None) -> Rect:
        """Take a band of that height off the top of what is left, and `gap` under it (= `band_gap` unless said)."""
        if getattr(self, "_frozen", False):
            raise RuntimeError("the frame is settled; everything else divides `body`")
        if height > self._remaining.height:
            raise PageFullError(
                f"asked for {height} EMU of height, {self._remaining.height} left — "
                "a page that does not fit is a page that needs splitting, not shrinking"
            )
        band, rest = self._remaining.rows([height, max(self._remaining.height - height, 1)])
        gap = self.theme.spacing.band_gap if gap is None else gap
        self._remaining = Rect(rest.left, band.bottom + gap, rest.width, self._remaining.bottom - band.bottom - gap)
        return band

    def _take_at(self, top: int, height: int, gap: int) -> Rect:
        """Take a band of that height starting at that height of the slide (= the title, where the layout puts it), and `gap` under it."""
        if getattr(self, "_frozen", False):
            raise RuntimeError("the frame is settled; everything else divides `body`")
        rest = self._remaining
        if top + height + gap >= rest.bottom:
            raise PageFullError(
                f"the title band ends at {top + height} EMU, and the page ends at {rest.bottom} — "
                "a page that does not fit is a page that needs splitting, not shrinking")
        band = Rect(rest.left, top, rest.width, height)
        self._remaining = Rect(rest.left, band.bottom + gap, rest.width, rest.bottom - band.bottom - gap)
        return band

    def _take_bottom(self, height: int) -> Rect:
        if getattr(self, "_frozen", False):
            raise RuntimeError("the frame is settled; everything else divides `body`")
        if height > self._remaining.height:
            raise PageFullError(f"asked for {height} EMU of height, {self._remaining.height} left")
        top = Rect(self._remaining.left, self._remaining.top, self._remaining.width,
                   self._remaining.height - height - self.theme.spacing.band_gap)
        strip = Rect(self._remaining.left, self._remaining.bottom - height, self._remaining.width, height)
        self._remaining = top
        return strip

    # -- the things a page may contain ---------------------------------------

    def _title_bar(self, title: str, kicker: str, sticker: str = "") -> None:
        """The title, the small words above it, the sticker beside it, and the line under them.

        ⚠ **題の帯は、題が折れる行ぶんの高さを取る。**1 行ぶんで固定していた間は、2 行に折れた題が
        帯から下へはみ出し、本体の最初の物に重なった (= 枠どうしは離れているので、検査は掴まない)。
        1 行の題の帯は今までの高さのままで、折れた行ごとに 1 行ぶん伸びる。題の上の小さい字は
        伸びない (= 伸びたぶんは全部題のもの)。

        ⚠ **題の上の小さい字の段は、その字の大きさで決まる** (= `kicker_height`)。帯を題と 1:2 に
        割っていた間は、小さい字だけを大きくした案件で、小さい字が題の頭に乗った。

        ⚠ **字と札は、レイアウトが印字する物の手前で止まる** (= `Theme.title_band`)。帯を頁の幅いっぱいに
        使っていた間は、右上にロゴの在るテンプレートで、長い題と札がロゴに乗った。

        ⚠ **題の上の小さい字は、資料によっては題の左に同じ行で置く** (= `[theme] kicker = "beside"`。
        差し色の太字で、題の 1 行目に)。帯の高さは上に置く時と同じで、題はそのぶん狭い幅で折れる。
        **題の枠の中に、題と同じ段落の頭の字として置く** (= `Lead`)。別の枠に置いて縦の中央を揃えていた間は、
        小さい字を題より小さくすると、字の下の線が題の下の線より上に浮いた。

        ⚠ **折れた題が、レイアウトが頁を横切って描く線に乗るなら止まる。**横切る物は幅を詰めても
        避けられず、題の帯が伸びても動かない (= 2 行目が題の下の罫線に乗った。映す資料で出た)。

        ⚠ **題の帯の下にレイアウトの罫線が残る頁は、その下から続ける** (= `Theme.under_the_title`)。字の小さい
        使い方の頁は帯が低く、本文が罫線より上から始まって箱が罫線に乗った。その頁では題の下の線を自分では
        引かない (= 線はレイアウトのもの 1 本)。

        札は題の帯の右端に、題の字の枠の真ん中の高さで置く (= 題は枠の真ん中に寄るので、何行に折れても
        札と題が揃う)。**題の字の枠は、札と、札との間の空きのぶん狭い** (= 題が札の下へ回り込まない。
        行もその幅で数える)。
        """
        t, s, p = self.theme.type, self.theme.spacing, self.theme.palette
        tag = self.theme.sticker_width(sticker) if sticker else 0
        lines, left, right = self.theme.title_band(title, sticker, kicker)
        lead = self.theme.kicker_lead(kicker)
        longest = self.theme.unbreakable(title, t.title, bold=True)
        if lead and right - left - lead - 2 * s.text_inset < longest:
            raise PageFullError(
                f"the kicker {kicker!r} leaves the title no room beside it for its longest word — "
                "beside a title it is a number and a word or two, not a sentence")
        if tag and right - left - lead - tag - s.gap_m - 2 * s.text_inset < longest:
            raise PageFullError(
                f"the sticker {sticker!r} leaves the title no room for its longest word — "
                "a sticker is a word or two (= draft, illustrative), not a sentence")
        folded = (lines - 1) * self.theme.line_height(t.title)
        if self.theme.under.title and self.theme.under.title_frame is not None:
            # レイアウトの題の枠の高さに置く (= 複製した頁の題と同じ高さ)。上に置く小さい字は、その枠の上に
            top, height = self.theme.title_row()
            above = s.kicker_height if kicker and not lead else 0
            bar = self._take_at(max(top - above, self.theme.slide.top), height + above + folded, s.title_gap)
        else:
            bar = self._take_top(s.title_height + folded, s.title_gap)
        # 字と札が使うのは、レイアウトが印字する物 (= ロゴ) の手前まで。帯そのものは頁の幅のまま
        clear = Rect(left, bar.top, right - left, bar.height)
        if kicker and not lead:
            kick, main = clear.split_top(s.kicker_height)
            self.elements.append(Text("kicker", kick, kicker, self.theme.kicker_size, p.muted))
        else:
            main = clear
        # 題の 1 行目の頭 (= 題は枠の真ん中に寄るので、折れた行ぶんの高さを引いて半分)
        row = self.theme.line_height(t.title)
        first = main.top + max((main.height - lines * row) // 2, 0)
        # ⚠ **レイアウトの線が題の 1 行目の字を横切るなら止まる** (= 取り消し線に見える)。題の帯を題の枠に
        # 合わせても残るのは、題の枠そのものを線が横切る雛形か、題の枠を持たないレイアウト。直せるのは、
        # 型の頁を乗せるレイアウトの方
        # 字の高さ (= 行の高さから行間を除いた、字が実際に立つ所)。線が行間だけを通るなら取り消し線にはならない
        size = self.theme.pt(t.title)
        glyph = max((row - size) // 2, 0)
        struck = self.theme.crossing_line(Rect(main.left, first + glyph, main.width, size))
        if struck is not None:
            name, line = struck
            raise PageFullError(
                f"the layout draws {repr(name) if name else 'a line'} at {(line.top + line.height // 2) / 914400:.2f} in "
                "from the top, through the title — it would read struck through. Put the declared pages on the "
                "layout of a specimen page whose title sits clear of it (`[theme] layout_of_page`)")
        if lines > 1:
            # ⚠ **折れて増えた行が、レイアウトが頁を横切って描く物 (= 題の下の罫線) に掛かるなら止まる。**
            # 帯は下へ伸びるが、レイアウトの線は動かない。幅を詰めても避けられないので、直せるのは題の長さだけ。
            # 1 行の題は止めない (= 題を短くしても直らない頁を、ここで止めない)
            if self.theme.crossed(Rect(main.left, first + row, main.width, (lines - 1) * row)):
                raise PageFullError(
                    f"the title folds to {lines} lines, and the lines it folds onto land on a line the "
                    "layout draws across the page — say it shorter, so it stays on one line")
        words = Rect(main.left, main.top, main.width - (tag + s.gap_m if tag else 0), main.height)
        beside = Lead(kicker, self.theme.kicker_size, p.accent, lead) if lead else None
        self.elements.append(Text("title", words, title, t.title, p.ink, bold=True, lead=beside))
        lower = self.theme.under_the_title(bar) - self._remaining.top
        if lower > 0:
            # レイアウトの罫線が、残りの始まる所より下に在る頁: 残りはその線の下から。題の下の線は自分では引かない
            if lower >= self._remaining.height:
                raise PageFullError("a line the layout draws across the page leaves no room under the title")
            self._remaining = self._remaining.inset(top=lower)
        else:
            # 題の字の下から帯の足元のすぐ下までに、レイアウトが頁を横切る線を引いていれば、それが題の下の線
            # (= 道具の線を重ねると 2 本になる)
            foot = first + (lines - 1) * row + glyph + size
            if self.theme.crossing_line(Rect(bar.left, foot, bar.width, bar.bottom + s.gap_m - foot)) is None:
                line = Rect(bar.left, bar.bottom, bar.width, s.hairline)
                start, end = self.theme.clear(line)
                self.elements.append(Fill("rule", Rect(start, line.top, end - start, line.height), p.rule))
        if tag:
            # 灰の細枠に灰の字 (= 頁の中身より一段うしろに引いた見た目)。地は塗らない
            tall = self.theme.line_height(t.body) + 2 * s.bar_pad_y
            self.elements.append(Bar(
                "sticker", Rect(main.right - tag, main.top + max((main.height - tall) // 2, 0), tag, tall),
                sticker, t.body, p.muted, outline=p.muted))

    def _band(self, text: str, *, conclusion: bool = False) -> None:
        """A declared condition (top) or the reading to take away (bottom).

        `band_look = "outlined"` の帯は枠と色を持つ。上 (= 条件) は差し色のごく薄い地に差し色の枠と太字、
        下 (= 結論) は灰のごく薄い地に灰の枠と本文の色の太字 ― 上は頁が前提にする読み、下は読み手に
        持ち帰らせる言葉で、下は本文の大きさ (= 上より一段小さい)。

        ⚠ **帯は、文が折れる行ぶんの高さを取る** (= 題の帯と同じ)。1 行ぶんで固定していた間は、2 行に折れた
        文の 2 行目が帯の枠の下へはみ出して描かれ、枠どうしは重ならないので検査も掴まなかった。1 行の帯は
        今までの高さのままで、折れた行ごとに 1 行ぶん伸びる。
        """
        p, t, s = self.theme.palette, self.theme.type, self.theme.spacing
        outlined = self.theme.band_look == "outlined"
        size = t.body if outlined and conclusion else t.band
        bold = outlined or conclusion
        # 字が使える幅 (= 帯の内側の余白と、文字の枠の左右の余白を除く)
        room = self._remaining.width - 2 * s.pad - 2 * s.text_inset
        folded = (self.theme.wraps(text, room, size, bold=bold) - 1) * self.theme.line_height(size)
        rect = (self._take_bottom(s.conclusion_height + folded) if conclusion
                else self._take_top(s.band_height + folded))
        if outlined:
            hue = p.muted if conclusion else p.accent
            self.elements.append(Fill("band", rect, p.thinned(p.BAND_WASH, hue), outline=hue, rounded=True))
            self.elements.append(Text("band_text", rect.inset(s.pad), text, size,
                                      p.ink if conclusion else hue, bold=bold))
            return
        self.elements.append(Fill("band", rect, p.rule if conclusion else p.band))
        self.elements.append(
            Text("band_text", rect.inset(s.pad), text, size, p.ink, bold=bold)
        )

    def ground(self, tone: str, points: float | None = None, bold: bool = False) -> tuple[str, str, str]:
        """(the fill, the colour of words on it, the colour of its edge) for a tone.

        `points` と `bold` は、その地に載せる字の大きさと太さ (= 書かなければ本文の大きさ、太字でない)。
        字の色は大きさと太さで下限が変わる (= `Palette.words_on`)。同じ地に大きさの違う字が載るなら、
        小さい方で渡す。

        Dark grounds take the paper's colour for their words and no edge; light grounds take
        an edge, or they melt into whatever lies behind them.
        """
        p = self.theme.palette
        if tone == PAPER:
            # 紙の色そのものは自分の枠を導けない (= 白の枠は白) ので、列の地の枠を借りる
            return p.paper, p.ink, p.edge(p.wash)
        if tone in LIGHT:
            fill = getattr(p, tone)
            return fill, p.ink, p.edge(fill)
        # 濃い役の地と、案件が意味の名前を付けた地: 字は読める方の色、本文の色の字が乗る薄い地は枠を持つ
        # (= 差し色は案件が変えるので、濃いとは限らない。白を決め打つと薄い差し色で字が溶けた)
        fill = ({"accent": p.accent, "good": p.good, "bad": p.bad}[tone] if tone in TONES
                else dict(self.theme.grounds)[tone])
        words = p.words_on(fill, self.theme.type.body if points is None else points, bold)
        return fill, words, p.edge(fill) if words == p.ink else ""

    def _legend_layout(self, rect: Rect, entries: list[tuple[str, int]], *, down: bool = False):
        """Where each entry of a legend goes: (name, left, top, width) per entry, in rows of as many columns as fit.

        項は (言葉, 見本の幅)。列は段をまたいで揃う (= 同じ列の見本は同じ左、同じ段は同じ上。名前の長さが違っても
        段どうしの見本がずれない)。列の幅はその列でいちばん広い項で、入る列の数のうち一番多い物を取る (= 1 段に
        収まる凡例は、詰めて並べた今までのまま)。`down` は 1 列 (= 上から下へ並べる)。
        """
        s = self.theme.spacing
        line = self.theme.line_height(self.theme.type.body)
        names = [name for name, _key in entries]
        wides = [key + s.gap_s + self.theme.width(name, self.theme.type.body) for name, key in entries]
        columns = 1 if down else self._legend_columns(wides, rect.width)
        widths = [max(wides[column::columns]) for column in range(columns)]
        lefts = [rect.left + sum(widths[:column]) + s.gap_m * column for column in range(columns)]
        for number, (name, wide) in enumerate(zip(names, wides)):
            yield name, lefts[number % columns], rect.top + line * (number // columns), wide

    def _legend_columns(self, wides: list[int], room: int) -> int:
        """How many columns a legend of entries this wide runs in at this width: the most that fit, at least one."""
        gap = self.theme.spacing.gap_m
        for columns in range(len(wides), 1, -1):
            if sum(max(wides[column::columns]) for column in range(columns)) + gap * (columns - 1) <= room:
                return columns
        return 1

    def legend_height(self, width: int, names: list[str], *, dotted: str = "", down: bool = False) -> int:
        """How tall a legend of these names (and the words of its dotted line, if any) runs at this width."""
        line = self.theme.line_height(self.theme.type.body)
        entries = _entries(names, dotted, self.theme.spacing.swatch)
        tops = [top for _n, _x, top, _w in self._legend_layout(Rect(0, 0, width, line), entries, down=down)]
        return max(tops) + line

    def legend_width(self, names: list[str], *, dotted: str = "") -> int:
        """How wide the longest entry of a legend runs (= what a legend set one name to a line needs)."""
        s = self.theme.spacing
        return max(key + s.gap_s + self.theme.width(name, self.theme.type.body) for name, key in _entries(names, dotted, s.swatch))

    def look(self, style: Style, points: float | None = None, bold: bool = False) -> Look:
        """How a box, a bar or an arrowhead is painted, from the looks every one of them takes.

        `tentative` (= 点線) は地を紙の色にし、字と枠を点線にする ― 決まった物の隣で同じ重さに見えないように。
        点線の色は資料の `tentative_look` が決める (= `muted` は灰、`toned` は色の役の色 ― 色の意味を保つ。
        読めない色の役は `tone_ink` が本文の色に倒す)。`strong` (= 強調) は枠を本文の色の太い線にする
        (= 地の色を変えずに目を集める)。
        """
        p = self.theme.palette
        if style.tentative:
            ink = self.tone_ink(style.tone, points, bold) if self.theme.tentative_look == "toned" else p.muted
            fill, outline = p.paper, ink
        else:
            fill, ink, outline = self.ground(style.tone, points, bold)
        if style.strong:
            outline = ink if style.tentative else p.ink
        return Look(fill, ink, outline, dashed=style.tentative, heavy=style.strong)

    def outlined_look(self, style: Style, points: float | None = None, bold: bool = False) -> tuple[Look, str]:
        """How a card is painted when its colour goes to its line (= `card_look = "outlined"`): the look, and the heading's colour.

        色を運ぶ役 (= `accent` / `good` / `bad`、作り付けの薄い地ほど紙に近くない地に名前を付けた物) は、地を
        色のごく薄い色にし、その色が枠を持つ。見出しの字は紙の上で読めればその色、読めない明るい色なら本文の色
        (= 本文は本文の色のまま)。色が意味を言う物は、塗らずに線と字で言う。意味を持たない薄い地 (= `box` /
        `band` / `tint`、それと同じくらい紙に近い地に名前を付けた物) は、もう「ほぼ紙の色に枠」なので今までのまま。`tentative` (= 内容未定) は本文の色の線と字 (= 色の役の外にある「まだ決まって
        いない」を、黒で言う。点線にはしない ― 色が言う)。資料の `tentative_look = "toned"` では、色の役の色の
        点線の枠と見出しで、地は紙の色 (= 色の意味を保ったまま、決まっていないと言う)。`strong` は線を太くする (= 色は変えない)。
        `points` と `bold` は、地に載る字の大きさと太さ (= `ground` と同じ。今までのままの地の判定に使う)。
        """
        p = self.theme.palette
        head = self.tone_ink(style.tone, points, bold)
        if style.tentative:
            if self.theme.tentative_look == "toned":
                return Look(p.paper, p.ink, head, dashed=True, heavy=style.strong), head
            return Look(p.paper, p.ink, p.ink, heavy=style.strong), p.ink
        fill = self.ground(style.tone, points, bold)[0]
        # 名前を付けた地は、作り付けの薄い地ほど紙に近くなければ色を運ぶ (= 枠がその色になる)。見出しの字は
        # 紙の上で読める色のまま (= 明るい色の字は紙に溶けるので、本文の色)
        if self.carries_colour(style.tone, points, bold) or (style.tone not in LIGHT and not p.pale(fill)):
            return Look(p.thinned(p.CARD_WASH, fill), p.ink, fill, heavy=style.strong), head
        return self.look(style, points, bold), head

    def carries_colour(self, tone: str, points: float | None = None, bold: bool = False) -> bool:
        """Whether a tone is a colour in itself (= `accent` / `good` / `bad`, a ground the project named that is deep), not a pale ground.

        薄い地 (= `box` / `band` / `tint`、字が本文の色で読める地に名前を付けた物) は、意味を持たない地の色。
        `points` と `bold` は `ground` と同じ (= 名前を付けた地が薄いかは、載る字の大きさと太さで決まる)。
        """
        return tone not in LIGHT and (tone in TONES or not self.ground(tone, points, bold)[2])

    def tone_ink(self, tone: str, points: float | None = None, bold: bool = False) -> str:
        """The colour words and lines take for a tone on the paper: the colour itself where the tone carries one, else the ink.

        カードの見出しの色 (= `outlined_look`)、文章の字の色、矢印の線の色が、この 1 つの決まりを読む。薄い地は
        紙の上の字にすると読めないので、本文の色のまま。
        """
        return self.ground(tone, points, bold)[0] if self.carries_colour(tone, points, bold) else self.theme.palette.ink

    def _lead(self, icon: tuple[Path, float] | None, size: float) -> int:
        """How much room the words give an icon set in front of them (= none without one)."""
        return self.theme.line_height(size) + self.theme.spacing.gap_s if icon else 0

    def _lead_icon(self, rect: Rect, left: int, icon: tuple[Path, float] | None, size: float) -> None:
        """Put an icon in front of a name inside a bar or an arrowhead, at the height of the words."""
        if not icon:
            return
        side = self.theme.line_height(size)
        source, aspect = icon
        square = Rect(left, rect.top + (rect.height - side) // 2, side, side)
        self.elements.append(Figure("icon", square.fit(aspect), Path(source), aspect))

    def legend(self, rect: Rect, names: list[str], *, dotted: str = "", down: bool = False) -> None:
        """What each named ground means: a swatch and its name, left to right (= `down`: top to bottom), in the order declared.

        `dotted` は点線の意味の言葉。書けば、凡例の終わりに点線の見本とその言葉を 1 項足す (= 見本の線は、矢印の
        点線と同じ色と太さ)。
        """
        t, s, p = self.theme.type, self.theme.spacing, self.theme.palette
        line = self.theme.line_height(t.body)
        entries = _entries(names, dotted, s.swatch)
        for number, (label, x, y, wide) in enumerate(self._legend_layout(rect, entries, down=down)):
            key = entries[number][1]
            if number < len(names):
                fill, _words, edge = self.ground(label)
                self.elements.append(Fill("swatch", Rect(x, y + (line - s.swatch) // 2, s.swatch, s.swatch),
                                          fill, outline=edge))
            else:
                self.line((x, y + line // 2), (x + key, y + line // 2), dashed=True)
            self.elements.append(Text("label", Rect(x + key + s.gap_s, y, wide - key - s.gap_s, line),
                                      label, t.body, p.ink))

    def boxes(self, rect: Rect, cards: list[Card], *, gap: int | None = None, top: bool = False) -> None:
        """Cards side by side inside an area you already divided off.

        地の色は箱ごとの `tone` (= `TONES`)。薄い地の箱は枠を持つ (= `ground`)。アイコンの
        在る箱は、左上にアイコン、文字はその右に置く。`card_look = "outlined"` の資料では、色を運ぶ箱は
        地ではなく枠と見出しの字で色を言い、角を丸め、字を縦の中央に置く (= `outlined_look`)。
        `top` は、どの資料でも字を箱の中の上端から置く (= 入れ物の見出しと同じ式。入れ物と並ぶカードの見出しが
        入れ物の見出しと同じ高さに並ぶ。札は 1 行なので中央のまま)。

        見出しも本文も省ける (= 本文だけのカード、空のカード)。`align = "center"` は字を中央寄せにし、
        本文の各行を「•」の行にもできる。札 (= `tag`) は薄い灰の地に、色の役の色の枠と太字を 1 行で置く。

        ⚠ **見出しの高さは字数で決める。**比で割っていた間は、2 行に折り返した見出しが
        本文の上に乗った (= 焼いて初めて出た。枠の中に収まっているので検査は通る)。
        """
        t, s, p = self.theme.type, self.theme.spacing, self.theme.palette
        columns = rect.columns(len(cards), gap if gap is not None else s.gap_m)
        for card, said in zip(columns, cards):
            heading, body = said.heading, said.body
            # 見出しと本文は同じ色の字 ― 本文があれば本文 (= 小さい方、太字でない)、無ければ太字の見出し
            size = (t.body, False) if body else (t.heading, True)
            outlined = self.theme.card_look == "outlined"
            look, head_ink = self.outlined_look(said.style, *size) if outlined else (self.look(said.style, *size), None)
            ink = look.ink
            if said.tag:
                # 札: 地は薄い灰、枠と字は色の役の色 (= 塗りのカードの資料でも同じ見た目)
                mark, ink = self.outlined_look(said.style, t.tag, True)
                head_ink = ink
                self.elements.append(Fill("box", card, p.wash, outline=mark.outline,
                                          heavy=mark.heavy, rounded=outlined))
            else:
                self.elements.append(Fill("box", card, look.fill, outline=look.outline,
                                          dashed=look.dashed, heavy=look.heavy, rounded=outlined))
            inner = card.inset(s.pad)
            if said.style.icon:
                # ⚠ アイコンは頁の図解に数えない (= 図の要る頁が、アイコンだけで通らないように)
                source, aspect = said.style.icon
                square = Rect(inner.left, inner.top, s.icon, s.icon)
                self.elements.append(Figure("icon", square.fit(aspect), Path(source), aspect))
                inner = inner.inset(left=s.icon + s.gap_s)
            head_ink = ink if head_ink is None else head_ink
            align = "center" if said.tag else said.align
            head_tall, body_tall = card_text(self.theme, said, max(inner.width - 2 * s.text_inset, 1))
            # 字が 1 つだけ (= 札、本文だけ、見出しだけ) なら、字の枠は箱の内側いっぱいで、縦の中央揃えが置く
            middle = outlined and not top
            alone = (middle or said.tag) and not (heading and body)
            if alone:
                head = rest = inner
            elif middle:
                # 字の塊 (= 見出しと本文) の真ん中を、箱の真ん中に置く
                total = head_tall + (s.gap_s if head_tall and body_tall else 0) + body_tall
                # 字の頭は枠の上端から `TEXT_INSET_Y` 下がるので、そのぶん枠を上げて塊の真ん中を箱の真ん中に合わせる
                start = inner.top + max((inner.height - total) // 2, 0) - TEXT_INSET_Y
                head = Rect(inner.left, start, inner.width, head_tall)
                rest = Rect(inner.left, head.bottom + (s.gap_s if head_tall else 0), inner.width, body_tall)
            elif body and heading:
                head, rest = inner.split_top(min(head_tall, max(inner.height - s.gap_s, 1)), gap=s.gap_s)
            else:
                head = rest = inner
            if body:
                self.elements.append(Text("box_body", rest, body, t.body, ink, align=align, bullets=said.bullets,
                                          middle=alone))
            if heading:
                self.elements.append(Text("box_heading", head, heading, t.tag if said.tag else t.heading, head_ink,
                                          bold=True, align=align, middle=alone))

    def _panel_heading_height(self, panel: Panel, width: int) -> int:
        """How tall the heading of a panel stands at this width of its inside (= 0 without one)."""
        if not panel.heading:
            return 0
        room = max(width - 2 * self.theme.spacing.text_inset, 1)
        return self.theme.wrapped_height(panel.heading, room, self.theme.type.heading, bold=True)

    def panel_head(self, panel: Panel, width: int) -> int:
        """How far under the top of a panel's inside the rows it holds begin (= 0 for a panel without a heading).

        `width` は箱の中の幅 (= 箱の幅から左右の `pad` を引いた幅)。置く側 (= `panel`) と、段の高さを数える側
        (= `compose`) が同じ数を使う。線は字の塊のすぐ下に引く (= 字の頭は枠の上端から `TEXT_INSET_Y` 下がる)。
        """
        tall = self._panel_heading_height(panel, width)
        if not tall:
            return 0
        s = self.theme.spacing
        return tall + (TEXT_INSET_Y + s.hairline if panel.rule else 0) + s.gap_s

    def reads_ink(self, style: Style) -> bool:
        """Whether words in the body's ink read straight on the ground a box of this style paints.

        濃い地の箱 (= 塗りのカードの資料で、差し色などの役の箱) は、字を紙の色で置く。箱が自分で持つ字は
        それで読めるが、箱の中へ直に置かれる別の字は本文の色なので、読めない。
        """
        if self.theme.card_look == "outlined" or style.tentative:
            return True
        return self.look(style, self.theme.type.body).ink == self.theme.palette.ink

    def panel(self, rect: Rect, panel: Panel) -> Rect:
        """A box that holds others, with its heading in the top left corner; the room left inside it.

        見た目は資料の `card_look` に従い、カードと同じ決まりを読む (= `outlined_look` / `look`)。
        `outlined` の資料では、色を運ぶ役の箱は色のごく薄い地に色の枠と見出し、角は丸い。塗りの資料では、
        役の地を塗る。見出しは大きさがカードの見出しの役で太字、色は箱の字の色。`rule` の線は見出しの色で、
        太さは細い線。返すのは中に段を割る枠 (= 見出しと線の下)。

        ⚠ **箱の中の字の色は、箱の地で決まらない。**ここで返す枠に置かれる字が読めるかは `reads_ink` が言う。
        """
        t, s = self.theme.type, self.theme.spacing
        outlined = self.theme.card_look == "outlined"
        # 見出しの下に字が置かれる箱なので、地は本文の大きさの字で決める (= 同じ地の字は小さい方で渡す)
        look, head_ink = (self.outlined_look(panel.style, t.body, False) if outlined
                          else (self.look(panel.style, t.body, False), None))
        if head_ink is None:
            head_ink = look.ink
        self.elements.append(Fill("panel", rect, look.fill, outline=look.outline,
                                  dashed=look.dashed, heavy=look.heavy, rounded=outlined))
        inner = rect.inset(s.pad)
        tall = self._panel_heading_height(panel, inner.width)
        head = self.panel_head(panel, inner.width)
        if head >= inner.height:
            raise PageFullError(
                f"a panel has {inner.height} EMU of height inside and its heading takes {head} — nothing is "
                "left for what it holds; a taller cell, a shorter heading, or no heading; nothing will shrink")
        if tall:
            self.elements.append(Text("panel_heading", Rect(inner.left, inner.top, inner.width, tall),
                                      panel.heading, t.heading, head_ink, bold=True))
            if panel.rule:
                self.elements.append(Fill("rule", Rect(inner.left, inner.top + TEXT_INSET_Y + tall,
                                                       inner.width, s.hairline), head_ink))
        return inner.inset(top=head)

    def figure(self, rect: Rect, source: Path | str, aspect: float, *, caption: str = "") -> Rect:
        """An image, kept at its own aspect ratio inside the area given.

        ⚠ **名は絵の下辺に付ける。**枠の下に固定していた間は、縦横比で縮んだぶんだけ
        絵と名が離れ、どの絵の名なのか読めなくなった。

        ⚠ **名のために取るのは、名が折れる行ぶんだけ。**枠の高さの 7 分の 1 を取って真ん中に
        置いていた間は、縦に長い枠ほど名が絵から離れて浮いた (= 段とマスで組んだ頁で焼いて出た)。

        ⚠ **絵に下限が在る** (= アイコンの一辺)。高さが足りずにそれより低くなる絵は置かずに止まる。

        ⚠ **名を取った残りが無ければ止まる。**残りを 1 EMU に切り上げて置いていた間は、高さ 0 の絵が
        書き出され、頁には名だけが残った (= 字を大きくして、絵の場所が名の高さを下回った頁で出た)。
        """
        t, p, s = self.theme.type, self.theme.palette, self.theme.spacing
        area, tall = rect, 0
        if caption:
            tall = self.theme.caption_height(caption, rect.width)
            if rect.height <= tall + s.gap_s:
                raise PageFullError(
                    f"a picture has {rect.height} EMU of height and its name alone takes {tall + s.gap_s} — "
                    "nothing is left for the picture; take something off the page, or drop the name")
            area, _rest = rect.split_top(rect.height - tall - s.gap_s)
        # ⚠ **高さで詰められた絵が、`figure_floor` (= 書かなければアイコンの一辺) より低くなるなら止まる。**縮むのは絵の性質だが、アイコンの
        # 一辺より低い絵は、もう図として読めない。横に長い絵が幅いっぱいで低いのは、詰められたのではない
        if area.height < s.figure_floor and area.width > area.height * aspect:
            raise PageFullError(
                f"a picture is left {area.height} EMU of height, less than the {s.figure_floor} a picture stands "
                "(= `figure_floor`) — "
                "too small to read as a picture; take something off the page, or split it in two")
        placed = area.fit(aspect)
        self.elements.append(Figure("figure", placed, Path(source), aspect, frame=area))
        self._figures += 1
        if caption:
            strip = Rect(rect.left, placed.bottom + s.gap_s, rect.width, tall)
            size, bold = self.theme.caption_face()
            self.elements.append(Text("caption", strip, caption, size, p.ink if bold else p.muted, bold=bold,
                                      align="center"))
        return placed

    def chart(self, chart: Chart) -> None:
        """A chart, already worked out (= `types/bodies/chart.py` decides what is drawn and how).

        グラフは頁の図解に数える (= 数字を形で見せている)。
        """
        self.elements.append(chart)
        self._figures += 1

    def table(self, rect: Rect, rows: list[list[str]], *, header: bool = True,
              highlight: dict[tuple[int, int], str] | None = None) -> Rect:
        """A small table. Empty cells are refused: write a dash if there is no value.

        セルは言葉か、状態の印 (= `Mark`) か、地の濃さを言った言葉 (= `Shade`。値の大小を地の濃さで見せる)。
        行は、列のセルの並びか、全部の列をまたぐ区切り (= `Band` 1 つの行。何を分けるかは `tone` が言う)。

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
        marks = frozenset((r, c) for r, row in enumerate(rows) for c, cell in enumerate(row)
                          if isinstance(cell, Mark))
        shades = {(r, c): cell.level for r, row in enumerate(rows) for c, cell in enumerate(row)
                  if isinstance(cell, Shade) and cell.level}
        if header and any(r == 0 for r, _c in shades):
            raise ValueError(
                "a heading cell is given a shade — the heading row stands on the accent already; "
                "a shade belongs to the cells under it")
        bands = {r: self._divider(row[0]) for r, row in enumerate(rows) if divides(row)}
        if header and 0 in bands:
            raise ValueError("the heading row of a table is cells in columns — a band divides the rows under it")
        self.elements.append(
            Table("table", placed, tuple(tuple(str(c) for c in row) for row in rows),
                  header, highlight or {}, tuple(widths), marks, shades, bands)
        )
        return placed

    def _divider(self, band: Band) -> tuple[str, str]:
        """(the ground, the colour of the words) of a row that divides a table.

        `tone` を書かない区切りは、見出しと同じ灰の地に本文の色。書いた区切りは、箱と同じ語彙で色を言う ―
        `table_look = "accent"` の表では箱と同じく地を塗り (= 差し色は濃い地に読める字)、`"plain"` の表では
        枠を色で言うカードと同じく色を字が持つ (= 地はほぼ紙の色)。
        """
        t, p = self.theme.type, self.theme.palette
        if not band.tone:
            return p.wash, p.ink
        named = self.theme.ground_names()
        if band.tone not in TONES and band.tone not in named:
            grounds = f"; this project names {', '.join(named)} in [theme.grounds]" if named else ""
            raise ValueError(
                f"band {str(band)!r} has tone {band.tone!r} — a tone is one of the palette's roles: "
                f"{', '.join(TONES)}{grounds}")
        if self.theme.table_look == "plain":
            look, words = self.outlined_look(Style(tone=band.tone), t.body, True)
            return look.fill, words
        fill, words, _edge = self.ground(band.tone, t.body, True)
        return fill, words

    def text_face(self, role: str | None = None) -> tuple[float, bool]:
        """(size, bold) of the words of a `text` in this role (= the side that counts its height and the side that sets it read one).

        書かなければ本文 (= 本文の大きさ、太字でない)。`label` は列や行の見出し (= `stage` の大きさの太字)、`note` は
        添える小さい字 (= `caption` の大きさ)、`display` は頁の主役の数字 (= `Type.display` の太字)。
        """
        t = self.theme.type
        return {"display": (t.display, True), "label": (t.stage, True), "note": (t.caption, False)}.get(
            role, (t.body, False))

    def text(self, rect: Rect, text: str, *, role: str | None = None, tone: str | None = None,
             align: str = "left") -> None:
        """Words that are part of what the page says: the body's colour, at the body's size.

        `role` は字の大きさと太さ (= `text_face`)。色は、書かなければ役ごと (= 本文と見出しは本文の色、`note` は
        灰、`display` は差し色)。`tone` を書けばその色の役の字 (= `tone_ink`)。
        """
        p = self.theme.palette
        size, bold = self.text_face(role)
        colour = self.tone_ink(tone, size, bold) if tone else {"note": p.muted, "display": p.accent}.get(role, p.ink)
        self.elements.append(Text("display" if role == "display" else "text", rect, text, size, colour,
                                  bold=bold, align=align))

    def display(self, rect: Rect, text: str, *, tone: str | None = None, align: str = "left") -> None:
        """The figure the page is about, set very large (= `Type.display`): bold, in the accent."""
        self.text(rect, text, role="display", tone=tone, align=align)

    def code_height(self, width: int, text: str) -> int:
        """How tall a block of code stands: its lines as written, with the room of a box round them.

        ⚠ **折らない。**コードとコマンドは、行の途中で折ると別の意味になる (= 字下げも桁も崩れる)。
        いちばん長い行が枠に入らなければ止まる (= 行を短くするか、マスを広げる)。
        """
        s, t = self.theme.spacing, self.theme.type
        lines = str(text).split("\n")
        widest = max(self.theme.width(line, t.body, family=MONO_FACE) for line in lines)
        room = width - 2 * (s.pad + s.text_inset)
        if widest > room:
            raise PageFullError(
                f"a line of code runs {widest} EMU and the box holds {room} — lines of code are not "
                "broken; shorten the line, or give the cell more width")
        return len(lines) * self.theme.line_height(t.body) + 2 * s.pad

    def code(self, rect: Rect, text: str) -> None:
        """Lines of code, a command or an equation: monospaced, as written, on a light ground with its edge."""
        s, t = self.theme.spacing, self.theme.type
        fill, ink, edge = self.ground("band")
        self.elements.append(Fill("code_box", rect, fill, edge))
        self.elements.append(Text("code", rect.inset(left=s.pad, right=s.pad, top=s.pad, bottom=s.pad),
                                  str(text), t.body, ink, family=MONO_FACE))

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
        lines = self._point_lines(items)
        if not lines:
            raise ValueError(
                "points was given nothing to say — drop the block rather than "
                "leaving an empty one"
            )
        self.elements.append(Text("points", rect, "\n".join(lines), t.body, p.ink))

    @staticmethod
    def _point_lines(items: list[str]) -> list[str]:
        """The lines `points` writes: a dash before each, its leading spaces kept, blank ones dropped."""
        # 先頭の空白は階層なので残す (= 落とすと章と小項目が同じ並びに潰れる)
        return [f"{' ' * (len(str(item)) - len(str(item).lstrip()))}\u2014 {str(item).strip()}"
                for item in items if str(item).strip()]

    def _voice_rows(self, width: int, voices: list["Voice"]) -> tuple[int, list[list["Voice"]]]:
        """(how many stand side by side, the voices row by row) at this width."""
        gap = self.theme.spacing.gap_m
        most = max(1, min(len(voices), (width + gap) // (VOICE_WIDTH + gap)))
        # 行の数は幅で決まる数のまま、1 行に並ぶ数を均す (= 6 つを 5 つと 1 つにせず、3 つずつ)
        across = -(-len(voices) // -(-len(voices) // most))
        return across, [voices[start:start + across] for start in range(0, len(voices), across)]

    def _voice_heights(self, width: int, voices: list["Voice"]) -> tuple[int, list[tuple[int, int]]]:
        """(how many across, and for every row: the height of its bubbles and of the whole row)."""
        t, s = self.theme.type, self.theme.spacing
        across, rows = self._voice_rows(width, voices)
        room = max((width - s.gap_m * (across - 1)) // across - 2 * s.pad, 1)
        heights = []
        for row in rows:
            bubble = max(self.theme.wrapped_height(voice.text, room) for voice in row) + 2 * s.pad
            who = self.theme.line_height(t.caption) if any(voice.who for voice in row) else 0
            heights.append((bubble, bubble + s.gap_m + who))
        return across, heights

    def voices_height(self, width: int, voices: list["Voice"]) -> int:
        """How tall `voices` stands at this width (= every row, and the gaps between them)."""
        _across, heights = self._voice_heights(width, voices)
        return sum(whole for _bubble, whole in heights) + self.theme.spacing.gap_m * (len(heights) - 1)

    def voices(self, rect: Rect, voices: list["Voice"]) -> None:
        """What people said, each in a speech bubble with who said it under its tail.

        ⚠ **吹き出しは 1 つの図形** (= 尾の付いた角丸の矩形。PowerPoint の「角丸四角形吹き出し」)。字は
        その中に持たせ、人が動かしても尾と字が離れない。尾は左下へ、誰の声かはその尾の先の下に小さく。
        1 行に並ぶ数はマスの幅で決まり (= `VOICE_WIDTH`)、行どうしで数を均す。同じ行の吹き出しは一番高い
        ものに揃う。

        ⚠ **見出しは持たない。**カードで声を置いていた間は、短い声 1 つにも見出しの行が付いて箱が高くなり、
        数の札と同じ見た目で「声」だと目に入らなかった。
        """
        if not voices:
            raise ValueError("voices was given no one's words — drop the cell rather than leaving it empty")
        t, s, p = self.theme.type, self.theme.spacing, self.theme.palette
        needed = self.voices_height(rect.width, voices)
        if needed > rect.height:
            raise PageFullError(f"the voices need {needed} EMU of height and have {rect.height} — "
                                "fewer or shorter voices, or a cell of their own")
        across, heights = self._voice_heights(rect.width, voices)
        _across, rows = self._voice_rows(rect.width, voices)
        top = rect.top
        for row, (bubble, whole) in zip(rows, heights):
            for cell, voice in zip(Rect(rect.left, top, rect.width, whole).columns(across, s.gap_m), row):
                look = self.look(voice.style, t.body)
                self.elements.append(Bar("voice", Rect(cell.left, cell.top, cell.width, bubble), voice.text,
                                         t.body, look.ink, fill=look.fill, outline=look.outline,
                                         align="left", shape="voice"))
                if voice.who:
                    self.elements.append(Text(
                        "voice_who", Rect(cell.left + s.pad, cell.top + bubble + s.gap_m,
                                          cell.width - s.pad, self.theme.line_height(t.caption)),
                        voice.who, t.caption, p.muted))
            top += whole + s.gap_m

    def points_height(self, width: int, items: list[str]) -> int:
        """How tall `points` stands at this width, counted on the lines it writes."""
        room = max(width - 2 * self.theme.spacing.text_inset, 1)
        return sum(self.theme.wrapped_height(line, room) for line in self._point_lines(items))

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

    def bar(self, rect: Rect, text: str, style: Style = Style(), *, size: float | None = None) -> None:
        """Something that takes a stretch of time, with its name on it.

        `style.tone` は地の色の役 (= `TONES`。箱と同じ語彙)。薄い地の棒は、地を濃くした色の枠を持つ ―
        列の薄い地の上に置かれるので、枠が無いと端が背景に溶ける。資料の `bar_look = "outlined"` では、
        色を運ぶ役の棒は地ではなく枠で色を言い、地・枠・字の色はカードの `outlined` と同じ決まり
        (= `outlined_look`) を読む。
        `style.tentative` は**点線の枠** (= 在れば / 内容未定)。地は紙の色なので、決まった棒の
        隣に置いても同じ重さに見えない ― 塗らずに透かすと、後ろを通る日付の線が名前を貫く。

        ⚠ **文字は棒の中に持たせる** (= 別の枠にしない)。人が PowerPoint で棒を動かすとき、
        文字が置き去りにならない。アイコンは名前の前に、字の高さで置く。
        """
        size = self.theme.type.body if size is None else size
        look = self.outlined_look(style, size)[0] if self.theme.bar_look == "outlined" else self.look(style, size)
        # アイコンの幅は置く前に決まる (= 字の高さ)。先に測って、棒は 1 度で書く
        self.elements.append(Bar("bar", rect, text, size, look.ink, fill=look.fill, outline=look.outline,
                                 dashed=look.dashed, heavy=look.heavy, lead=self._lead(style.icon, size)))
        self._lead_icon(rect, rect.left + self.theme.spacing.bar_pad_x, style.icon, size)

    def chevron(self, rect: Rect, text: str, style: Style, *, shape: str, size: float) -> None:
        """One stage of a road to a goal: an arrowhead with its name inside it.

        `shape` は `home` (= 最初の段、左が平ら) か `chevron` (= 2 段目から、左が切り欠き)。
        アイコンは名前の前に、切り欠きの内側から置く。
        """
        look = self.look(style, size, True)
        self.elements.append(Bar("chevron", rect, text, size, look.ink, fill=look.fill, outline=look.outline,
                                 dashed=look.dashed, heavy=look.heavy, bold=True, shape=shape,
                                 lead=self._lead(style.icon, size)))
        notch = self.theme.spacing.chevron_point if shape == "chevron" else 0
        self._lead_icon(rect, rect.left + notch + self.theme.spacing.bar_pad_x, style.icon, size)

    def span(self, rect: Rect, text: str, *, size: float | None = None) -> None:
        """What a stretch of periods is like (= movable, fixed), laid over the columns."""
        p = self.theme.palette
        size = self.theme.type.body if size is None else size
        self.elements.append(Bar("span", rect, text, size, p.ink, fill=p.rule))

    def period(self, rect: Rect, name: str, *, size: float | None = None) -> None:
        """What one column of a timeline is called, in a cell of its own (= a table's heading row)."""
        p = self.theme.palette
        size = self.theme.type.body if size is None else size
        self.elements.append(Bar("period", rect, name, size, p.words_on(p.accent, size, True),
                                 fill=p.accent, bold=True))

    def stripe(self, rect: Rect) -> None:
        """The faint ground under every other column, so the eye can follow a period down the page."""
        self.elements.append(Fill("stripe", rect, self.theme.palette.wash))

    def line(self, start: tuple[int, int], end: tuple[int, int], *, arrow: bool = False,
             tone: str | None = None, corners: Sequence[tuple[int, int]] = (),
             hops: Sequence[tuple[int, int]] = (), hop: int = 0, begins_on: tuple[Rect, int] | None = None,
             ends_on: tuple[Rect, int] | None = None, dashed: bool = False) -> None:
        """A thin line in the colour of quiet ink (= what joins things, not a thing itself).

        `tone` を書けば、その色の役の線 (= `tone_ink`)。矢じりも線と同じ色。`corners` は始まりと終わりの間の曲がり角
        (= 頁の上の点。順に、横と縦を交互に進む直角の折れ線)。`hops` は、別の線と交わってこの線が半径 `hop` の
        半円で跳び越す所 (= この線の上の点)。`begins_on` と `ends_on` は、線の両端が付く箱とその辺 (= 辺の真ん中から
        出入りする曲がる線が、箱を動かすと付いて来るように)。
        """
        points = [start, *corners, end]
        if corners or hops:
            for first, second in zip(points, points[1:]):
                if first[0] != second[0] and first[1] != second[1]:
                    raise ValueError(f"a bent line runs along an axis between its corners: {first} to {second} does not")
        left, right = min(x for x, _ in points), max(x for x, _ in points)
        top, bottom = min(y for _, y in points), max(y for _, y in points)
        self.elements.append(Line("line", Rect(left, top, right - left, bottom - top), start, end,
                                  self.tone_ink(tone) if tone else self.theme.palette.muted, arrow=arrow,
                                  corners=tuple((x - start[0], y - start[1]) for x, y in corners),
                                  hops=tuple((x - start[0], y - start[1]) for x, y in hops), hop=hop if hops else 0,
                                  begins_on=begins_on, ends_on=ends_on, dashed=dashed))

    def words(self, rect: Rect, text: str, size: float, *, bold: bool = False, align: str = "center") -> None:
        """Words that name a part of a diagram (= a circle's name, what two circles share, a mark on a picture)."""
        self.elements.append(Text("diagram_text", rect, text, size, self.theme.palette.ink, bold=bold, align=align))

    def circle(self, rect: Rect, tone: str, *, clear: float = 0.0) -> None:
        """A circle on the ground of a tone, with that ground's edge."""
        fill, _words, edge = self.ground(tone)
        self.elements.append(Ellipse("circle", rect, fill, edge, clear))

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
              size: float | None = None, bold: bool | None = None) -> None:
        """A short name on one line: beside a bar or a mark, or at the head of a column.

        `role` は色の役 (= `ink` / `muted` / `accent`)。`accent` は頁を横切る日付の名前で、太字。
        `bold` を言えば、役に依らずその太さ (= 下へ流れる流れ図の、段の名前)。

        ⚠ **折り返さない。**隣の物に付く名前なので、長すぎれば横へ伸びる ― 2 行に折ると
        下の段に乗る。
        """
        p = self.theme.palette
        size = self.theme.type.body if size is None else size
        colour = {"ink": p.ink, "muted": p.muted, "accent": p.accent}[role]
        self.elements.append(Text("label", rect, text, size, colour,
                                  bold=role == "accent" if bold is None else bold, align=align))

    def lane(self, rect: Rect, name: str) -> None:
        """What one lane of a timeline is (= who, or which line of work)."""
        t, p = self.theme.type, self.theme.palette
        self.elements.append(Text("lane", rect, name, t.stage, p.ink, bold=True))

    def backdrop(self, rect: Rect, tone: str) -> None:
        """A ground laid under boxes (= the ground of its tone, with that ground's edge).

        背景なので、箱がその上に重なるのが正常 (= 入れ物の地と同じ)。置くのは箱より先 (= 下の層)。
        """
        fill, _words, edge = self.ground(tone)
        self.elements.append(Fill("backdrop", rect, fill, outline=edge))

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
