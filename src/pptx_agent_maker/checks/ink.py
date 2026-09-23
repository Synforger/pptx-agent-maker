"""What a shape actually puts on the page — not the box it was given.

⚠ **枠と、描かれる物は別。**テキストの枠は中身より広く取られているのがふつうで、
中央寄せや右寄せならなおさら空く。枠どうしで重なりを見ると、**画面では離れている物が
重なりとして上がる** ― 前の世代の検査は、そうやって上がったものがほとんど
誤検出で、最後は「自作の頁だけ見る」という逃げ方で黙らせていた。

ここが返すのは**行ごとの矩形**。折り返しと寄せを勘定して、文字が乗る帯だけを出す。
見積もりなので**狭い側へ外す** (= 迷ったら描かないほうに倒す)。重なりを言うのは
「それでも重なっている」ときだけにする。
"""

from __future__ import annotations

import html
import re

from .slide import Shape

#: pptx の既定の内余白 (= 左右 0.1 inch / 上下 0.05 inch)
LEFT_INSET = RIGHT_INSET = 91440
TOP_INSET = BOTTOM_INSET = 45720
#: 1 pt = 12700 EMU
PER_POINT = 12700
#: 行の高さ (= 級数に対する比。描画の実測に近い側へ)
LINE = 1.2
#: 大きさを書いていない run の既定 (= レイアウトから継ぐので測れない。小さめに見る)
ASSUMED_SIZE = 12.0

PARAGRAPH = re.compile(r"<a:p>(.*?)</a:p>", re.S)
RUN = re.compile(r"<a:r>(.*?)</a:r>", re.S)
SIZE = re.compile(r'<a:rPr[^>]*\bsz="(\d+)"')
TEXT = re.compile(r"<a:t\b[^>]*(?<!/)>(.*?)</a:t>", re.S)
ALIGN = re.compile(r'<a:pPr[^>]*\balgn="(\w+)"')
ANCHOR = re.compile(r'<a:bodyPr[^>]*\banchor="(\w+)"')
INSETS = {name: re.compile(rf'<a:bodyPr[^>]*\b{name}="(-?\d+)"')
          for name in ("lIns", "rIns", "tIns", "bIns")}
#: ⚠ 塗りは**その図形の spPr の中**だけを見る。範囲を閉じないと、文字の色指定
#: (= run の solidFill) まで「枠に塗りがある」と読んでしまう。
SHAPE_PROPERTIES = re.compile(r"<p:spPr[ >](.*?)</p:spPr>", re.S)
SOLID_FILL = re.compile(r"<a:solidFill>")
NO_FILL = re.compile(r"<a:noFill\s*/>")
OUTLINE = re.compile(r"<a:ln[ >].*?<a:solidFill>", re.S)
PLACEHOLDER = re.compile(r"<p:ph[ />]")


Box = tuple[int, int, int, int]


def _wide(character: str) -> bool:
    """全角として数えるか (= 半角は約半分の幅で並ぶ)."""
    return ord(character) > 0x2E7F


def _width_of(text: str, size: float) -> int:
    em = size * PER_POINT
    return round(sum(em if _wide(c) else em * 0.5 for c in text))


def _lines(pieces: list[tuple[str, float]], usable: int) -> list[tuple[int, float]]:
    """Break a paragraph the way a box of this width would: (width, tallest size) per line.

    ⚠ **級数は run ごとに違う。**段落の最初の run で全部を数えると、大きな数字の隣の
    小さな添え字まで大きく数えて折り返し、実際には 1 行の物が 2 行ぶんの高さになる
    (= 「1,024 MB」のような大小の混ざった文字がそれで、下の注記に掛かっていると報告された)。
    """
    lines: list[tuple[int, float]] = []
    width, tallest = 0, 0.0
    for text, size in pieces:
        for character in text:
            step = _width_of(character, size)
            if usable > 0 and width + step > usable and width:
                lines.append((width, tallest))
                width, tallest = 0, 0.0
            width += step
            tallest = max(tallest, size)
    lines.append((width, tallest or ASSUMED_SIZE))
    return lines


def _paragraphs(xml: str) -> list[tuple[list[tuple[str, float]], str]]:
    """(runs, alignment) per paragraph that actually prints something."""
    found = []
    for body in PARAGRAPH.findall(xml):
        pieces: list[tuple[str, float]] = []
        for run in RUN.findall(body):
            text = html.unescape("".join(TEXT.findall(run)))
            if not text:
                continue
            declared = SIZE.search(run)
            pieces.append((text, int(declared.group(1)) / 100 if declared else ASSUMED_SIZE))
        if not "".join(text for text, _ in pieces).strip():
            continue
        align = ALIGN.search(body)
        found.append((pieces, align.group(1) if align else "l"))
    return found


def _inset(xml: str, name: str, fallback: int) -> int:
    found = INSETS[name].search(xml)
    return int(found.group(1)) if found else fallback


def has_body(shape: Shape) -> bool:
    """True when the shape puts something on the page other than text.

    ⚠ **塗りも線も無い枠は「見えない」** ― 文字を置くためだけの器なので、枠として
    重なっていても画面には何も無い。
    """
    if shape.kind != "sp":
        return True  # 絵と表は枠いっぱいに描かれる
    properties = SHAPE_PROPERTIES.search(shape.xml)
    inside = properties.group(1) if properties else ""
    if NO_FILL.search(inside) and not OUTLINE.search(inside):
        return False
    return bool(SOLID_FILL.search(inside) or OUTLINE.search(inside))


def draws_anything(shape: Shape) -> bool:
    """True unless the shape is a placeholder, which prints nothing by itself.

    ⚠ **レイアウトのプレースホルダは器**で、頁が中身を入れなければ何も出ない。器の枠は
    版面いっぱいに取られていることが多く、実体として数えると頁の全要素が「下敷きに
    重なっている」ことになる。

    ⚠ **器が文字を持っていても同じ** ― `Click to edit Master title style` のような
    見本の文字はマスターを編集する画面にしか出ない。頁がその器を使えば、中身は頁の側の
    図形として在る。

    ⚠ **見ないと決めたもの: 頁番号の器。**中身は機械が入れるので実際に印字されるが、
    器は右下に広く取られていて、実際に出るのは数桁。器の幅で見ると前の世代と同じ
    誤検出になり (= どれも番号のだいぶ左で終わっていた)、数桁ぶんを
    見積もろうとすると**器がレイアウトとマスターに二重に在って位置が合わない**。
    右下の隅に本文が届く頁は版面の外れとして `off_page` が見る。
    """
    return not PLACEHOLDER.search(shape.xml)


def ink_of(shape: Shape) -> list[Box]:
    """The rectangles this shape actually covers."""
    box: Box = (shape.left, shape.top, shape.right, shape.bottom)
    if has_body(shape):
        return [box]

    paragraphs = _paragraphs(shape.xml)
    if not paragraphs:
        return []

    left = shape.left + _inset(shape.xml, "lIns", LEFT_INSET)
    right = shape.right - _inset(shape.xml, "rIns", RIGHT_INSET)
    usable = right - left
    rows: list[tuple[int, float, str]] = []
    for pieces, align in paragraphs:
        rows += [(width, size, align) for width, size in _lines(pieces, usable)]

    height = sum(round(size * PER_POINT * LINE) for _, size, _ in rows)
    top = shape.top + _inset(shape.xml, "tIns", TOP_INSET)
    floor = shape.bottom - _inset(shape.xml, "bIns", BOTTOM_INSET)
    room = floor - top
    anchor = ANCHOR.search(shape.xml)
    where = anchor.group(1) if anchor else "t"
    if where == "ctr":
        top += max((room - height) // 2, 0)
    elif where == "b":
        top += max(room - height, 0)

    marks: list[Box] = []
    y = top
    for width, size, align in rows:
        step = round(size * PER_POINT * LINE)
        width = min(width, usable)
        if align == "ctr":
            x = left + (usable - width) // 2
        elif align == "r":
            x = right - width
        else:
            x = left
        # ⚠ **枠の外へは伸ばさない。**見積もりが実際より大きく出たとき、外へ伸びた分が
        # 下の枠に掛かって重なりに見える。枠から出る文字は別の検査 (= off_page) の担当。
        bottom = min(y + step, floor)
        if bottom > y:
            marks.append((x, y, x + width, bottom))
        y += step
    return marks

