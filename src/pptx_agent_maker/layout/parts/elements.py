"""Everything that can be placed on a page, as data.

頁に積まれる物は全部ここの形で、焼く層 (= `write/`) はこの形だけを読む。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..base.geometry import Rect


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
class Figure(Element):
    source: Path
    aspect: float


class Mark(str):
    """A status mark in a table cell (= a Harvey ball, or good / partly / bad): one character.

    文字のまま表を通るので、幅も高さもほかのセルと同じ数え方で測られ、寄せもほかのセルと同じ。
    印であることだけを型で持ち、置く時に、印の字形を持つ書体で書く。
    """


@dataclass(frozen=True)
class Table(Element):
    rows: tuple[tuple[str, ...], ...]
    header: bool = True
    highlight: dict[tuple[int, int], str] = field(default_factory=dict)
    #: 列ごとの幅 (= 中身の長さで配る。空なら均等)
    widths: tuple[int, ...] = ()
    #: 状態の印が入っているセル (= 行, 列)
    marks: frozenset[tuple[int, int]] = frozenset()


@dataclass(frozen=True)
class Series:
    """One series of a chart, as it is drawn (= every colour and format already decided)."""

    name: str
    #: 項目ごとの値。None は「この項目には無い」(= 棒も数字も出ない)
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
