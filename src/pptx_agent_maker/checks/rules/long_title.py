"""A title that runs past two lines, on a page copied or imported.

題は結論の文で、2 行まで。3 行に達した題は、読む前に頁の上 3 分の 1 を使い、題だけを順に読んで話を
追う読み方 (= `titles`) ができなくなる。

ここが見るのは**題のプレースホルダを持つ頁** (= テンプレートから複製した頁と、過去のデッキから輸入
した頁)。宣言で組んだ頁の題は、焼いた file からはどれが題か分からないので、宣言の側で同じ名前の
検査が見る (= `declared/long_title.py`)。

⚠ **測れない題は赤にしない。**プレースホルダは位置も文字の大きさもレイアウトから継ぐ。どちらかが
頁にもレイアウトにもマスターにも書かれていなければ、行は数えられない。
"""

from __future__ import annotations

import re
from pathlib import Path

from ..base.finding import Finding
from ..base.ink import LEFT_INSET, RIGHT_INSET, lines_in
from ..base.slide import EXTENT, TEXT, TITLE_PLACEHOLDER, BuiltSlide, read

NAME = "long_title"
#: 題が取ってよい行の数
LIMIT = 2

_SIZE = re.compile(r'\bsz="(\d+)"')
_TITLE_STYLE = re.compile(r"<p:titleStyle>(.*?)</p:titleStyle>", re.S)


def off(config: dict | None) -> bool:
    """A project may switch the check off (= `[checks] long_title = false`)."""
    return (config or {}).get(NAME, True) is False


def _width(title: str, page: BuiltSlide) -> int | None:
    """How wide the title's box is: as the page says, else as the placeholder it sits on says."""
    own = EXTENT.search(title)
    if own:
        return int(own.group(1))
    return next((shape.width for shape in page.beneath if TITLE_PLACEHOLDER.search(shape.xml)), None)


def _size(page: BuiltSlide) -> float | None:
    """The size a title inherits: from the placeholder it sits on, else the master's title style."""
    for shape in page.beneath:
        found = _SIZE.search(shape.xml) if TITLE_PLACEHOLDER.search(shape.xml) else None
        if found:
            return int(found.group(1)) / 100
    for part in page.under:
        style = _TITLE_STYLE.search(part)
        found = _SIZE.search(style.group(1)) if style else None
        if found:
            return int(found.group(1)) / 100
    return None


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    if off(config):
        return []
    findings: list[Finding] = []
    for page in read(deck):
        title = page.title()
        if title is None:
            continue
        width, size = _width(title, page), _size(page)
        if width is None or (size is None and not _SIZE.search(title)):
            continue
        lines = lines_in(title, width - LEFT_INSET - RIGHT_INSET, size)
        if lines > LIMIT:
            words = " ".join(TEXT.findall(title)).strip()
            findings.append(Finding(NAME, page.number, words[:60], why(lines)))
    return findings


def why(lines: int) -> str:
    return f"the title runs to {lines} lines — a title is {LIMIT} at most; say it shorter"
