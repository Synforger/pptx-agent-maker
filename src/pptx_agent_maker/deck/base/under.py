"""Reading what a declared page will sit on, out of the specimen.

型で組む頁は白紙に描いてから、テンプレートの 1 枚目のレイアウトへ向け直す (= `pages/slides.py`)。
描く側がそのレイアウトを知らなかった間は、レイアウトに題の枠が在っても題は自前の文字の枠で書かれ
(= テンプレートから複製した頁の題と色が揃わない)、題の帯は頁の幅いっぱいに取られて右上のロゴに乗った。

ここが読むのは 2 つだけ ― **題の枠が在るか**と、**何が印字されるか**。

⚠ **印字される物の数え方は、重なりの検査と同じ関数を使う** (= `checks/base/ink.py`)。別々に数えると、
描く側が避けた物と、検査が「乗っている」と言う物が食い違う。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from ...checks.base.ink import draws_anything, ink_of
from ...checks.base.slide import TEXT_SHAPE, shapes_in
from ...layout.base.geometry import Rect
from ...layout.base.tokens import Under

#: 型の頁が乗るレイアウト (= `pages/slides.py` が向け直す先)
LAYOUT = "ppt/slideLayouts/slideLayout1.xml"
_MASTER = re.compile(r'Target="\.\./slideMasters/(slideMaster\d+\.xml)"')
#: 本文の頁の題の枠。表紙の題 (= `ctrTitle`) は数えない ― 真ん中に大きく置く題の見た目を、本文の頁の
#: 題が継ぐことになる
_TITLE = re.compile(r'<p:ph\b[^>]*\btype="title"')


def under_of(specimen: Path | str) -> Under:
    """What the first layout of a specimen offers a declared page, and what it prints.

    読めない見本は「何も無い」と読む (= 題は今までどおり自前で書かれ、帯は頁の幅のまま)。
    """
    parts: list[str] = []
    try:
        with zipfile.ZipFile(Path(specimen)) as archive:
            parts.append(archive.read(LAYOUT).decode("utf-8"))
            rels = archive.read(LAYOUT.replace("slideLayouts/", "slideLayouts/_rels/") + ".rels").decode("utf-8")
            for master in _MASTER.findall(rels):
                parts.append(archive.read(f"ppt/slideMasters/{master}").decode("utf-8"))
    except (KeyError, OSError, zipfile.BadZipFile):
        if not parts:
            return Under()

    title = any(_TITLE.search(body) for body in TEXT_SHAPE.findall(parts[0]))
    prints = tuple(
        Rect(left, top, right - left, bottom - top)
        for part in parts for shape in shapes_in(part) if draws_anything(shape)
        for left, top, right, bottom in ink_of(shape) if right > left and bottom > top)
    return Under(title=title, prints=prints)
