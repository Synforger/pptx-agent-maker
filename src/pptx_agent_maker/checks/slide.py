"""Reading a built slide back out of the file.

宣言層は置く前に解くが、**複製と輸入で入ってきた頁は座標を誰も保証していない** ―
過去のデッキから来た頁は、その週の誰かが手で置いたもの。焼いたものを読み直す口が要る。

python-pptx を使わず XML を読むのは、`deck/` と同じ理由 (= 複製・輸入が部品を直に触るので、
検査も同じ層で見た方が、見ているものが 1 つになる)。
"""

from __future__ import annotations

import html
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

SHAPE = re.compile(r"<p:(sp|pic|graphicFrame)>(.*?)</p:\1>", re.S)
OFFSET = re.compile(r'<a:off x="(-?\d+)" y="(-?\d+)"/>')
EXTENT = re.compile(r'<a:ext cx="(\d+)" cy="(\d+)"/>')
RUN = re.compile(r"<a:r>(.*?)</a:r>", re.S)
SIZE = re.compile(r'<a:rPr[^>]*\bsz="(\d+)"')
# ⚠ 自己終了の <a:t/> を「開始タグ」と読むと、次の </a:t> まで飲んで XML ごと
# 中身として拾う (= 実物で 1 回踏んだ)。直前が / でない > だけを開始とみなす。
TEXT = re.compile(r"<a:t\b[^>]*(?<!/)>(.*?)</a:t>", re.S)
CELL = re.compile(r"<a:tc[ >](.*?)</a:tc>", re.S)
ROW = re.compile(r"<a:tr[ >](.*?)</a:tr>", re.S)


@dataclass(frozen=True)
class Shape:
    """One shape as the file has it."""

    kind: str
    left: int
    top: int
    width: int
    height: int
    xml: str

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def texts(self) -> list[str]:
        return [html.unescape(t) for t in TEXT.findall(self.xml)]

    def type_sizes(self) -> list[float]:
        """Point sizes written on runs that carry text.

        ⚠ 大きさを書いていない run は、レイアウトの既定を継ぐので**ここでは測れない**。
        測れないものを赤にしない (= 誤検出は「黙らせるためだけの直し」を書かせる)。
        """
        sizes: list[float] = []
        for body in RUN.findall(self.xml):
            if not html.unescape("".join(TEXT.findall(body))).strip():
                continue
            declared = SIZE.search(body)
            if declared:
                sizes.append(int(declared.group(1)) / 100)
        return sizes

    def table_rows(self) -> list[list[str]]:
        """Cell texts, row by row, for a table; empty for anything else."""
        return [[html.unescape("".join(TEXT.findall(cell))) for cell in CELL.findall(row)]
                for row in ROW.findall(self.xml)]


@dataclass(frozen=True)
class BuiltSlide:
    """One page of a built deck."""

    number: int
    name: str
    xml: str

    def shapes(self) -> list[Shape]:
        found: list[Shape] = []
        for kind, body in SHAPE.findall(self.xml):
            offset, extent = OFFSET.search(body), EXTENT.search(body)
            if not (offset and extent):
                continue
            found.append(Shape(kind, int(offset.group(1)), int(offset.group(2)),
                               int(extent.group(1)), int(extent.group(2)), body))
        return found

    def texts(self) -> list[str]:
        return [html.unescape(t) for t in TEXT.findall(self.xml)]


def read(deck: Path) -> list[BuiltSlide]:
    """Every page of a built deck, in reading order."""
    deck = Path(deck)
    with zipfile.ZipFile(deck) as archive:
        presentation = archive.read("ppt/presentation.xml").decode("utf-8")
        rels = archive.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
        file_of = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"', rels))
        order = [file_of[rid] for rid in re.findall(r'<p:sldId[^>]*r:id="(rId\d+)"', presentation)
                 if rid in file_of]
        return [BuiltSlide(number, name, archive.read(f"ppt/slides/{name}").decode("utf-8"))
                for number, name in enumerate(order, start=1)]


def slide_size(deck: Path) -> tuple[int, int]:
    """The deck's page size in EMU."""
    with zipfile.ZipFile(Path(deck)) as archive:
        presentation = archive.read("ppt/presentation.xml").decode("utf-8")
    match = re.search(r'<p:sldSz[^>]*cx="(\d+)"[^>]*cy="(\d+)"', presentation)
    if not match:
        raise ValueError("the deck does not declare a slide size")
    return int(match.group(1)), int(match.group(2))
