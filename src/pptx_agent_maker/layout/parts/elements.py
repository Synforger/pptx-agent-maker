"""Everything that can be placed on a page, as data.

頁に積まれる物は全部ここの形で、焼く層 (= `write/`) はこの形だけを読む。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..base.geometry import Rect, pt


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
    #: この字だけの書体 (= 等幅の行)。空なら案件の書体
    family: str = ""
    #: 行ごとに「•」を付ける (= 段落の書式。折り返した行は点の分だけ字下げされる。`bullet_indent`)
    bullets: bool = False


#: 文字の枠が上下に自分で取る余白 (= pptx の既定。左右は `Spacing.text_inset`)。字を縦の中央に置く側 (= `Page.boxes`)
#: と、枠を書く側 (= `write/pptx.py`) が同じ値を使う。枠の上端から字の頭までの距離
TEXT_INSET_Y = 45720


def bullet_indent(size: float) -> int:
    """How far the words of a bullet stand in from the edge: one em, the bullet's own width and the gap after it.

    数える側 (= 折り返しの幅) と書く側 (= 段落の字下げ) が同じ値を使う。
    """
    return pt(size)


@dataclass(frozen=True)
class Fill(Element):
    colour: str
    #: 枠の色。空なら枠を引かない
    outline: str = ""
    dashed: bool = False
    #: 太い枠 (= 強調)
    heavy: bool = False
    #: 角を丸める (= 目次の章のカード)
    rounded: bool = False


@dataclass(frozen=True)
class Line(Element):
    """A straight line from one point to another. `rect` is the box round the two points.

    ⚠ **矢印は線の端の形で描く。**プリセットの矢印の図形 1 つで PowerPoint が修復を言い出した実例が
    在る (= 流れ図の向きを字で置く理由)。直線の端に付ける矢じりは線の書式で、図形の種類を増やさない。
    """

    start: tuple[int, int]
    end: tuple[int, int]
    colour: str
    #: 終わりの端に矢じりを付ける
    arrow: bool = False


@dataclass(frozen=True)
class Ellipse(Element):
    """A circle (or an ellipse) filling `rect`, its ground let through by `clear` (= 0 is solid)."""

    colour: str
    outline: str = ""
    #: 下の物が透けて見える割合 (= 重なった所が濃く見える)
    clear: float = 0.0


@dataclass(frozen=True)
class Figure(Element):
    source: Path
    aspect: float


class Mark(str):
    """A status mark in a table cell (= a Harvey ball, or good / partly / bad): one character.

    文字のまま表を通るので、幅も高さもほかのセルと同じ数え方で測られ、寄せもほかのセルと同じ。
    印であることだけを型で持ち、置く時に、印の字形を持つ書体で書く。
    """


class Shade(str):
    """Words in a table cell that stand on a ground as deep as the cell says (= `level` quarters of the accent).

    印と同じく、字のまま表を通る (= 幅も高さもほかのセルと同じに測られる)。濃さだけを持ち、置く時に
    地の色と、その上で読める字の色が決まる。
    """

    level: int

    def __new__(cls, words: str, level: int) -> "Shade":
        cell = super().__new__(cls, words)
        cell.level = level
        return cell


@dataclass(frozen=True)
class Table(Element):
    rows: tuple[tuple[str, ...], ...]
    header: bool = True
    highlight: dict[tuple[int, int], str] = field(default_factory=dict)
    #: 列ごとの幅 (= 中身の長さで配る。空なら均等)
    widths: tuple[int, ...] = ()
    #: 状態の印が入っているセル (= 行, 列)
    marks: frozenset[tuple[int, int]] = frozenset()
    #: 地の濃さを言ったセル: (行, 列) → 4 分の幾つか (= 0 は持たない)
    shades: dict[tuple[int, int], int] = field(default_factory=dict)
    #: 全部の列をまたぐ区切りの行: 行 → (地の色, 字の色)。行の中身は、区切りの字だけの 1 つのセル
    bands: dict[int, tuple[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Series:
    """One series of a chart, as it is drawn (= every colour and format already decided)."""

    name: str
    #: 項目ごとの値。None は「この項目には無い」(= 棒も数字も出ない)。点のグラフでは、点ごとの y
    values: tuple[float | None, ...]
    #: 塗りの色 (= 折れ線は線と点の色)。空なら描かない (= 滝グラフの、棒を浮かせるための台)
    colour: str = ""
    #: 項目ごとの塗り (= 1 つだけ目立たせる項目): (項目の番号, 色)
    points: tuple[tuple[int, str], ...] = ()
    #: 値の数字の書式 (= 表計算の書式)。空なら数字を出さない
    number_format: str = ""
    #: 値の数字の色。空ならグラフの字の色 (= 棒の中に置く数字は、地の上で読める方の色を書く)
    label_colour: str = ""
    #: 棒の枠の色。空なら枠を引かない (= 積み上げた段の境)
    outline: str = ""
    #: 点のグラフ (= `scatter`) の、点ごとの x (= `values` が y)。項目のグラフでは空
    xs: tuple[float, ...] = ()
    #: 点のグラフの、名前を付けた点の字 (= 点の横に置く言葉)。付けない点は持たない
    labels: tuple["Label", ...] = ()
    #: 点の印の大きさ (pt)。0 なら書き出す側の既定
    mark: float = 0


@dataclass(frozen=True)
class Label:
    """Words set beside one point of a chart of points (= its name, and its numbers under it)."""

    #: 何番目の点か
    index: int
    #: 言葉。改行で行を分ける
    text: str
    #: 点の左に置く (= 右に置くと、グラフの縁を越える点)
    left: bool = False
    #: 言葉の大きさ (pt)。0 ならグラフの字と同じ
    size: float = 0


@dataclass(frozen=True)
class Callout:
    """A few words pointing at one point of a chart: where they sit, and the thin line to the point."""

    text: str
    words: Rect
    #: 言葉から点へ引く細い線。言葉が点のすぐそばに在れば要らない (= None)
    line: Rect | None = None
    #: 言葉の寄せ。点を指す言葉は点の真上 (= 中央)、項目の名前の下に添える 1 行は軸に揃える (= 右)
    align: str = "center"
    #: 言葉の大きさと色。0 と空はグラフの字と同じ (= 添え書きだけ、小さく灰にする)
    size: float = 0
    colour: str = ""


@dataclass(frozen=True)
class Pinned:
    """The plot of a chart held in one place, so where a point falls can be worked out beforehand.

    ふつうのグラフは、描く範囲も値の軸の目盛りも PowerPoint が決める (= 数字を直せば付いて動く)。
    注記を持つグラフだけは、言葉と線を点に合わせて置くので、両方を道具が決めて書き出す。
    """

    #: 描く範囲 (= 軸と凡例を除いた、棒や線の入る矩形)。グラフの枠に対する比で x, y, 幅, 高さ
    inner: tuple[float, float, float, float]
    #: 値の軸の端から端と、目盛りの間
    low: float
    high: float
    step: float
    #: 項目どうしの間 (= 棒 1 本の幅に対する百分率)
    gap: int = 150


@dataclass(frozen=True)
class Plane:
    """The plot of a chart of points held in one place, so where a point falls can be worked out beforehand.

    `Pinned` の、2 本とも値の軸のグラフ版 (= 点の横の言葉や、行ごとの言葉の場所を、道具が計算する)。
    """

    #: 描く範囲 (= 軸の字や凡例を除いた矩形)。グラフの枠に対する比で x, y, 幅, 高さ
    inner: tuple[float, float, float, float]
    #: 横の軸と縦の軸の (下限, 上限, 目盛りの間)
    x: tuple[float, float, float]
    y: tuple[float, float, float]
    #: 横の軸を対数 (= 10 の累乗ごとに目盛り) にする
    log: bool = False
    #: 縦の軸を上から数える (= 最初の行が上)。横の軸の字は上に出る
    down: bool = False
    #: 横の軸の数字の書式 (= 表計算の書式)。空ならそのまま
    x_format: str = ""


#: グラフの描き方 (= 書き出すグラフの種類)。滝グラフは `stacked` で描く
PLOTS = ("bar", "column", "line", "stacked")


@dataclass(frozen=True)
class Chart(Element):
    """A chart a person can edit: its numbers travel inside the deck, and PowerPoint redraws from them."""

    plot: str = "column"
    categories: tuple[str, ...] = ()
    series: tuple[Series, ...] = ()
    #: グラフの中の字の大きさと色、軸の線の色
    size: float = 12
    colour: str = "000000"
    line: str = "000000"
    #: 凡例を出すか、値の軸 (= 目盛りの数字) を出すか
    legend: bool = False
    axis: bool = False
    #: グラフそのものの枠。注記を持つグラフは、`rect` のうち注記の言葉の場所を除いた残り (= 無ければ `rect`)
    frame: Rect | None = None
    pinned: Pinned | None = None
    callouts: tuple[Callout, ...] = ()
    #: 点のグラフ (= `scatter`) の軸の名前。項目のグラフでは空
    x_title: str = ""
    y_title: str = ""
    #: 値の軸の (下限, 上限, 目盛りの間)。在れば値の軸と目盛りの線を出す (= 無ければ軸は PowerPoint が決め、
    #: 目盛りの線は引かない)
    scale: tuple[float, float, float] | None = None
    #: 点のグラフの目盛りの線の色。空なら線は引かない
    grid: str = ""
    #: 点のグラフの描く範囲と軸を道具が決めて書く時の値 (= 無ければ PowerPoint が決める)
    plane: Plane | None = None


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
    #: 形 (= `SHAPES`)。矩形のほかは、道のりの段の矢羽根と、人の声の吹き出し
    shape: str = "rect"
    #: 太い枠 (= 強調)
    heavy: bool = False
    #: 文字の左に空ける幅 (= 名前の前に置いたアイコンのぶん)
    lead: int = 0


#: 文字を持つ図形の形。`home` は左が平らで右が尖る矢羽根 (= 道のりの最初の段)、`chevron` は
#: 左が切り欠かれて右が尖る矢羽根 (= 2 段目から)
SHAPES = ("rect", "home", "chevron", "voice")


@dataclass(frozen=True)
class Diamond(Element):
    """A point in time. `rect` is the square the diamond sits in."""

    colour: str
