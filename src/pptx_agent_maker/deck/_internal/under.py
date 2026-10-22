"""Reading what a declared page will sit on, out of the specimen.

型で組む頁は白紙に描いてから、テンプレートのレイアウトへ向け直す (= `pages/slides.py`)。向け直す先は、
案件が `[theme] layout_of_page` で名指した見本の頁が乗るレイアウトで、書いていなければ部品の名前が
`slideLayout1.xml` のレイアウト。

⚠ **既定は並びの 1 枚目ではなく、部品の名前で決まる。**書き出した道具によっては、`slideLayout1.xml` が
表紙の型で、本文の頁は別のレイアウトに乗っている (= Google スライドの書き出し)。型の頁が表紙の飾りの上に
乗ったので、本文の頁を 1 枚名指せば、その頁と同じレイアウトに乗る口を足した。頁の番号で名指すのは、
同じ名前のレイアウトが 2 つ在る雛形でも 1 つに決まるから。
描く側がそのレイアウトを知らなかった間は、レイアウトに題の枠が在っても題は自前の文字の枠で書かれ
(= テンプレートから複製した頁の題と色が揃わない)、題の帯は頁の幅いっぱいに取られて右上のロゴに乗った。

ここが読むのは 4 つだけ ― **題の枠が在るか、在ればどこか**、**何が印字されるか**、**頁に番号を振る資料か**、
**どのレイアウトか**。

⚠ **題の枠の場所は、題の帯の上下に使う。**道具の余白で帯を置いていた間は、マスターの題の枠が上の余白より
上に在る雛形で、題の下に引かれた太い罫線が題の字の真ん中を通った (= 取り消し線に見えた)。レイアウトの
題の枠が場所を書いていなければ、それが継ぐマスターの題の枠の場所。

⚠ **頁番号は、レイアウトに枠が在るだけでは振らない。**PowerPoint のレイアウトはほとんどが頁番号の枠を
持つが、番号が出るのは、頁の側がその枠を持つ時だけ (= 「スライド番号」を入れた資料)。見本の頁が 1 枚も
持たない資料で型の頁にだけ置くと、複製した頁には番号が無く、型の頁にだけ番号が出る ― 型の頁にだけ
番号が出なかった元の食い違いを、裏返しただけになる。見本の頁のどれかが持つ時に、型の頁も持つ。

⚠ **印字される物の数え方は、重なりの検査と同じ関数を使う** (= `checks/_internal/ink.py`)。別々に数えると、
描く側が避けた物と、検査が「乗っている」と言う物が食い違う。

⚠ **線だけは、ここが自分で読む。**レイアウトの罫線は、コネクタか、高さ (か幅) の無い図形で書かれる。
検査はコネクタを図形として読まず、厚みの無い物は重なりの許容に入って数えない ― 題の下の罫線に、
折れた題の 2 行目が乗っても、どちらも何も言わなかった。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from ...checks._internal.ink import NO_FILL, PLACEHOLDER, draws_anything, ink_of
from ..._common.slide import EXTENT, OFFSET, TEXT_SHAPE, shapes_in
from ..._common.archive import NUMBER_FRAME as _NUMBER
from ...layout.geometry import Rect
from ...layout.tokens import Under

#: 案件が何も名指さない時に、型の頁が乗るレイアウト (= 部品の名前)
DECLARED_LAYOUT = "slideLayout1.xml"
_LAYOUTS = "ppt/slideLayouts"
_MASTER = re.compile(r'Target="\.\./slideMasters/(slideMaster\d+\.xml)"')
#: 本文の頁の題の枠。表紙の題 (= `ctrTitle`) は数えない ― 真ん中に大きく置く題の見た目を、本文の頁の
#: 題が継ぐことになる
_TITLE = re.compile(r'<p:ph\b[^>]*\btype="title"')
_SAID = re.compile(r'([\w:]+)="([^"]*)"')
_PAGE = re.compile(r"ppt/slides/slide\d+\.xml")
#: 線になり得る図形 (= コネクタと、ふつうの図形)
_DRAWN = re.compile(r"<p:(cxnSp|sp)>(.*?)</p:\1>", re.S)
_NAME = re.compile(r'<p:cNvPr\b[^>]*\bname="([^"]*)"')
_SLIDE_TARGET = re.compile(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"')
_LISTED = re.compile(r'<p:sldId\b[^>]*r:id="(rId\d+)"')
_LAYOUT_TARGET = re.compile(r'Target="\.\./slideLayouts/(slideLayout\d+\.xml)"')
_STROKE = re.compile(r"<a:ln\b([^>]*)>(.*?)</a:ln>|<a:ln\b([^>]*)/>", re.S)
_WEIGHT = re.compile(r'\bw="(\d+)"')
#: 太さを書いていない線の太さ (= pptx の既定、0.75pt)
HAIRLINE = 9525


def _lines(part: str) -> list[tuple[str, Rect]]:
    """The straight lines one part draws, each by its name and as the thin rectangle it prints.

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
        name = _NAME.search(body)
        found.append((name.group(1) if name else "",
                      Rect(left - (0 if width else weight // 2), top - (0 if height else weight // 2),
                           width or weight, height or weight)))
    return found


def _title_frame(part: str) -> Rect | None:
    """Where one part puts its title placeholder, if it has one that says so."""
    for body in TEXT_SHAPE.findall(part):
        if _TITLE.search(body):
            offset, extent = OFFSET.search(body), EXTENT.search(body)
            if offset and extent:
                return Rect(int(offset.group(1)), int(offset.group(2)), int(extent.group(1)), int(extent.group(2)))
            return None
    return None


def layout_of_page(archive: zipfile.ZipFile, page: int) -> str:
    """The layout (= its part name) the Nth page of a specimen sits on, counted the way a reader counts.

    数えるのは頁を読む順 (= `sldIdLst`)。部品の名前 (= `slide7.xml`) は資料の作られ方の名残で、何枚目かを言わない。
    """
    presentation = archive.read("ppt/presentation.xml").decode("utf-8")
    file_of = dict(_SLIDE_TARGET.findall(archive.read("ppt/_rels/presentation.xml.rels").decode("utf-8")))
    order = [file_of[rid] for rid in _LISTED.findall(presentation) if rid in file_of]
    if not 1 <= page <= len(order):
        raise ValueError(f"theme.layout_of_page is {page}, and the specimen has {len(order)} pages")
    rels = archive.read(f"ppt/slides/_rels/{order[page - 1]}.rels").decode("utf-8")
    found = _LAYOUT_TARGET.search(rels)
    if found is None:
        raise ValueError(f"page {page} of the specimen sits on no layout")
    return found.group(1)


def under_of(specimen: Path | str, page: int | None = None) -> Under:
    """What the layout a declared page sits on offers it, and what it prints.

    `page` は、型の頁を乗せる見本の頁 (= その頁と同じレイアウトに乗る。None なら `DECLARED_LAYOUT`)。
    見本に無い頁を名指すと止める (= `ValueError`)。読めない見本は「何も無い」と読む (= 題は今までどおり自前で
    書かれ、帯は頁の幅のまま)。
    """
    parts: list[str] = []
    numbered = False
    layout = DECLARED_LAYOUT
    try:
        with zipfile.ZipFile(Path(specimen)) as archive:
            if page is not None:
                layout = layout_of_page(archive, page)
            parts.append(archive.read(f"{_LAYOUTS}/{layout}").decode("utf-8"))
            numbered = any(_NUMBER.search(archive.read(name).decode("utf-8"))
                           for name in archive.namelist() if _PAGE.fullmatch(name))
            rels = archive.read(f"{_LAYOUTS}/_rels/{layout}.rels").decode("utf-8")
            for master in _MASTER.findall(rels):
                parts.append(archive.read(f"ppt/slideMasters/{master}").decode("utf-8"))
    except (KeyError, OSError, zipfile.BadZipFile):
        if not parts:
            return Under(layout=layout)

    title = any(_TITLE.search(body) for body in TEXT_SHAPE.findall(parts[0]))
    seat = next((found for found in map(_title_frame, parts) if found is not None), None) if title else None
    prints = tuple(
        Rect(left, top, right - left, bottom - top)
        for part in parts for shape in shapes_in(part) if draws_anything(shape)
        for left, top, right, bottom in ink_of(shape) if right > left and bottom > top)
    lines = tuple(line for part in parts for line in _lines(part))
    frame = _NUMBER.search(parts[0]) if numbered else None
    return Under(title=title, prints=prints + tuple(rect for _, rect in lines),
                 number=tuple(_SAID.findall(frame.group(1))) if frame else (),
                 title_frame=seat, lines=lines, layout=layout)
