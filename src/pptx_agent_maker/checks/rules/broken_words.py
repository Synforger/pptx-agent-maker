"""A word broken in the middle: a run of letters wider than the box it is written in (= told without stopping a build).

英字と数字の語は空白でしか折れない。語が枠の字の幅より広いと、PowerPoint は語の途中で折る
(= 「ABCDEFGH / I」)。組み立ては通り、ほかの検査も通る ― 字は枠の中に収まっていて、重なりも
はみ出しも無いからだ。札の字をかな 4 字から英大文字 9 字の 1 語に替えた頁で、それが起きて誰も
言わなかった。

見るのは、折れる字の枠 (= `wrap="none"` でない `p:sp`) と表のマス。字が使える幅は、枠の幅から左右の
内余白と段落の字下げを引いた幅 (= 表はマスがまたぐ列の幅から、マスの左右の余白を引いた幅)。語の幅は
組む側と同じ字ごとの幅 (= `layout.tokens.advance`) で数える ― 組む側が「収まる」と言う幅と、
ここが「折れる」と言う幅が食い違わない。

⚠ **折れてよい所で割ってから測る。**語は空白と全角の字で区切り、ハイフンとスラッシュの後ろでも
区切る (= PowerPoint はそこで行を変える。`state-of-the-art` を 1 語として測ると、折れ目どおりに折れた
行まで当たる)。

⚠ **測れない語は言わない。**大きさを書いていない run はレイアウトから大きさを継ぐので、幅が分からない
(= 題のプレースホルダ)。その run を含む語は数えない。

止めずに知らせる (= 列の幅を広げるか、語を短くするかは書いた人が決める。案件で外すなら
`[checks] broken_words = false`)。
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from ...layout.tokens import advance
from ..finding import Finding
from .._internal.ink import LEFT_INSET, RIGHT_INSET
from ..._common.slide import Shape, read

NAME = "broken_words"
#: a hit is reported and ends neither `build` nor `check` with 1 (= `checks.stopping`)
STOPS = False
#: 1 cm = 360000 EMU (= 所見に出す幅の単位)
CM = 360000
#: 1 pt = 12700 EMU
PER_POINT = 12700

_BODY = re.compile(r"<p:txBody>(.*?)</p:txBody>", re.S)
_BODY_PROPERTIES = re.compile(r"<a:bodyPr\b[^>]*>")
_NO_WRAP = re.compile(r'\bwrap="none"')
_INSET = {side: re.compile(rf'\b{side}="(-?\d+)"') for side in ("lIns", "rIns")}
_SCALE = re.compile(r'<a:normAutofit\b[^>]*\bfontScale="(\d+)"')
_PARAGRAPH = re.compile(r"<a:p>(.*?)</a:p>|<a:p\b[^>]*>(.*?)</a:p>", re.S)
_PARAGRAPH_PROPERTIES = re.compile(r"<a:pPr\b[^>]*>")
_MARGIN = re.compile(r'\bmarL="(-?\d+)"')
_RUN = re.compile(r"<a:r>(.*?)</a:r>", re.S)
_RUN_PROPERTIES = re.compile(r"<a:rPr\b[^>]*>")
_SIZE = re.compile(r'\bsz="(\d+)"')
_BOLD = re.compile(r'\bb="(?:1|true)"')
_FACE = re.compile(r'<a:latin\b[^>]*\btypeface="([^"]*)"')
_TEXT = re.compile(r"<a:t\b[^>]*(?<!/)>(.*?)</a:t>", re.S)
_TABLE = re.compile(r"<a:tbl>(.*?)</a:tbl>", re.S)
_COLUMN = re.compile(r'<a:gridCol\b[^>]*\bw="(\d+)"')
_ROW = re.compile(r"<a:tr\b[^>]*>(.*?)</a:tr>", re.S)
_CELL = re.compile(r"<a:tc\b([^>]*)>(.*?)</a:tc>", re.S)
_SPAN = re.compile(r'\bgridSpan="(\d+)"')
_MERGED = re.compile(r'\b[hv]Merge="(?:1|true)"')
_CELL_PROPERTIES = re.compile(r"<a:tcPr\b[^>]*>")
_CELL_MARGIN = {side: re.compile(rf'\b{side}="(-?\d+)"') for side in ("marL", "marR")}
#: 折れてよい所 (= 空白の前後・全角の字の前後・ハイフンとスラッシュの後ろ)
_PIECES = re.compile(r"[^\s⺀-￿\-/]*[\-/]|[^\s⺀-￿\-/]+")

#: 1 字ずつ (= 字・大きさの pt・太字か・書体)。大きさが分からない字は None
Letter = tuple[str, float | None, bool, str]


def _attribute(pattern: re.Pattern, tag: re.Match | None, fallback: int) -> int:
    found = pattern.search(tag.group(0)) if tag else None
    return int(found.group(1)) if found else fallback


def _letters(paragraph: str, scale: float) -> list[Letter]:
    letters: list[Letter] = []
    for run in _RUN.findall(paragraph):
        properties = _RUN_PROPERTIES.search(run)
        size = _SIZE.search(properties.group(0)) if properties else None
        bold = bool(properties and _BOLD.search(properties.group(0)))
        face = _FACE.search(run)
        text = html.unescape("".join(_TEXT.findall(run)))
        points = int(size.group(1)) / 100 * scale if size else None
        letters += [(character, points, bold, face.group(1) if face else "") for character in text]
    return letters


def _too_wide(letters: list[Letter], usable: int) -> list[tuple[str, int]]:
    """The words of a paragraph wider than the room for words, each with its width (= measured ones only)."""
    text = "".join(letter[0] for letter in letters)
    found = []
    for piece in _PIECES.finditer(text):
        part = letters[piece.start():piece.end()]
        if any(points is None for _c, points, _b, _f in part):
            continue
        wide = round(sum(advance(c, bold, face) * points * PER_POINT for c, points, bold, face in part))
        if wide > usable:
            found.append((piece.group(0), wide))
    return found


def _paragraphs(body: str) -> list[tuple[str, int]]:
    """Each paragraph of a text body and how far it is indented."""
    found = []
    for match in _PARAGRAPH.finditer(body):
        paragraph = match.group(1) if match.group(1) is not None else match.group(2)
        found.append((paragraph, _attribute(_MARGIN, _PARAGRAPH_PROPERTIES.search(paragraph), 0)))
    return found


def _in_box(shape: Shape) -> list[tuple[str, int, int]]:
    """(word, its width, the room for words) for each word too wide for its text box."""
    body = _BODY.search(shape.xml)
    if not body:
        return []
    properties = _BODY_PROPERTIES.search(body.group(1))
    if properties and _NO_WRAP.search(properties.group(0)):
        return []
    scale = _SCALE.search(body.group(1))
    factor = int(scale.group(1)) / 100000 if scale else 1.0
    room = (shape.width - _attribute(_INSET["lIns"], properties, LEFT_INSET)
            - _attribute(_INSET["rIns"], properties, RIGHT_INSET))
    found = []
    for paragraph, indent in _paragraphs(body.group(1)):
        usable = room - indent
        found += [(word, wide, usable) for word, wide in _too_wide(_letters(paragraph, factor), usable)]
    return found


def _in_table(shape: Shape) -> list[tuple[str, int, int]]:
    """(word, its width, the room for words) for each word too wide for its cell of a table."""
    table = _TABLE.search(shape.xml)
    if not table:
        return []
    columns = [int(width) for width in _COLUMN.findall(table.group(1))]
    found = []
    for row in _ROW.findall(table.group(1)):
        column = 0
        for attributes, cell in _CELL.findall(row):
            span = int(_SPAN.search(attributes).group(1)) if _SPAN.search(attributes) else 1
            width = sum(columns[column:column + span])
            column += span
            if _MERGED.search(attributes) or not width:
                continue
            properties = _CELL_PROPERTIES.search(cell)
            room = (width - _attribute(_CELL_MARGIN["marL"], properties, LEFT_INSET)
                    - _attribute(_CELL_MARGIN["marR"], properties, RIGHT_INSET))
            for paragraph, indent in _paragraphs(cell):
                usable = room - indent
                found += [(word, wide, usable) for word, wide in _too_wide(_letters(paragraph, 1.0), usable)]
    return found


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    if (config or {}).get(NAME, True) is False:
        return []
    findings: list[Finding] = []
    for page in read(deck):
        for shape in page.shapes():
            if shape.kind not in ("sp", "graphicFrame"):
                continue
            for word, wide, usable in (_in_box(shape) if shape.kind == "sp" else _in_table(shape)):
                findings.append(Finding(
                    NAME, page.number, repr(word),
                    f"the word is {wide / CM:.2f} cm wide and its box has {max(usable, 0) / CM:.2f} cm for words, "
                    "so it breaks in the middle — a wider column or box, or a shorter word"))
    return findings
