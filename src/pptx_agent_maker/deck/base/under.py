"""Reading what a declared page will sit on, out of the specimen.

型で組む頁は白紙に描いてから、テンプレートの 1 枚目のレイアウトへ向け直す (= `pages/slides.py`)。
描く側がそのレイアウトを知らなかった間は、レイアウトに題の枠が在っても題は自前の文字の枠で書かれ
(= テンプレートから複製した頁の題と色が揃わない)、題の帯は頁の幅いっぱいに取られて右上のロゴに乗った。

ここが読むのは 2 つだけ ― **題の枠が在るか**と、**何が印字されるか**。

⚠ **印字される物の数え方は、重なりの検査と同じ関数を使う** (= `checks/base/ink.py`)。別々に数えると、
描く側が避けた物と、検査が「乗っている」と言う物が食い違う。

⚠ **線だけは、ここが自分で読む。**レイアウトの罫線は、コネクタか、高さ (か幅) の無い図形で書かれる。
検査はコネクタを図形として読まず、厚みの無い物は重なりの許容に入って数えない ― 題の下の罫線に、
折れた題の 2 行目が乗っても、どちらも何も言わなかった。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from ...checks.base.ink import NO_FILL, PLACEHOLDER, draws_anything, ink_of
from ...checks.base.slide import EXTENT, OFFSET, TEXT_SHAPE, shapes_in
from ...layout.base.geometry import Rect
from ...layout.base.tokens import Under

#: 型の頁が乗るレイアウト (= `pages/slides.py` が向け直す先)
LAYOUT = "ppt/slideLayouts/slideLayout1.xml"
_MASTER = re.compile(r'Target="\.\./slideMasters/(slideMaster\d+\.xml)"')
#: 本文の頁の題の枠。表紙の題 (= `ctrTitle`) は数えない ― 真ん中に大きく置く題の見た目を、本文の頁の
#: 題が継ぐことになる
_TITLE = re.compile(r'<p:ph\b[^>]*\btype="title"')
#: 線になり得る図形 (= コネクタと、ふつうの図形)
_DRAWN = re.compile(r"<p:(cxnSp|sp)>(.*?)</p:\1>", re.S)
_STROKE = re.compile(r"<a:ln\b([^>]*)>(.*?)</a:ln>|<a:ln\b([^>]*)/>", re.S)
_WEIGHT = re.compile(r'\bw="(\d+)"')
#: 太さを書いていない線の太さ (= pptx の既定、0.75pt)
HAIRLINE = 9525


def _lines(part: str) -> list[Rect]:
    """The straight lines one part draws, each as the thin rectangle it prints.

    線として読むのは、コネクタと、高さか幅の無い図形 (= 厚みを持つ図形は `ink_of` が数える)。
    線を引かないと書いてある物 (= `<a:ln><a:noFill/>`) と、線の指定も図形のスタイルも持たない図形は、
    何も印字しない。
    """
    found = []
    for kind, body in _DRAWN.findall(part):
        offset, extent = OFFSET.search(body), EXTENT.search(body)
        if PLACEHOLDER.search(body) or not (offset and extent):
            continue
        width, height = int(extent.group(1)), int(extent.group(2))
        if (kind == "sp" and width and height) or not (width or height):
            continue
        stroke = _STROKE.search(body)
        if stroke is None and "<p:style>" not in body:
            continue
        if stroke is not None and NO_FILL.search(stroke.group(2) or ""):
            continue
        said = _WEIGHT.search((stroke.group(1) or stroke.group(3) or "") if stroke else "")
        weight = int(said.group(1)) if said else HAIRLINE
        left, top = int(offset.group(1)), int(offset.group(2))
        found.append(Rect(left - (0 if width else weight // 2), top - (0 if height else weight // 2),
                          width or weight, height or weight))
    return found


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
    return Under(title=title, prints=prints + tuple(line for part in parts for line in _lines(part)))
