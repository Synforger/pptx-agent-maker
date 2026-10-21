"""Words too close in lightness to the ground they sit on.

宣言で組む頁は、地の色に合わせて字の色を選ぶ (= 明暗差の大きい方)。**外れるのは複製と輸入**で、
過去の回に人が選んだ色の組がそのまま来る。

地は、字の図形の塗り → 下に敷かれた図形の塗り (= 字の図形の中心を含む物のうち、いちばん上) →
頁・レイアウト・マスターの背景、の順に探す。表のセルは、そのセルの塗りが地。

⚠ **測れない物は言わない。**字の色を書いていない run (= レイアウトから継ぐ)、グラデーションや
絵の地、透過の掛かった色は、どの色に見えるかを決められない。

閾値は Web の読みやすさの基準 (= WCAG 2 の AA): 明暗差 4.5、大きい字 (= 18pt 以上、太字なら
14pt 以上) は 3。大きさを書いていない字は大きい側で数える (= 迷ったら言わない側へ)。値と大きさの決まりは
組む側と同じ物を読む (= `layout/base/tokens.py` の `READABLE` と `reading_floor`)。

**通してよい組は、字の色と地の色の組で書く** (= `[checks] contrast_allowed`)。テンプレートのブランドの
差し色 (= 差し色の地に白い字、白い地に差し色の字) は案件の側では動かせないが、検査ごと外すと
灰色の字のような本物の取りこぼしも見えなくなる。色 1 つで通す形にしないのは、その色を使う組の全部
(= 薄い灰色の地に差し色の字も) が黙って通るから。通した組は報告に 1 行ずつ出す (= `Findings.allowed`)。
案件で検査ごと外すなら `[checks] contrast = false`。
"""

from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path

from ...layout.base.tokens import ALLOWED, allowed_pairs
from ..base.colour import Palette, contrast, reading_floor, solid
from ..base.finding import Finding, Findings
from ..base.slide import RUN, TEXT, BuiltSlide, Shape, read

NAME = "contrast"

SHAPE_PROPERTIES = re.compile(r"<p:spPr\b[^>]*>(.*?)</p:spPr>", re.S)
OUTLINE = re.compile(r"<a:ln\b.*?</a:ln>", re.S)
UNREADABLE = re.compile(r"<a:(gradFill|blipFill|pattFill)\b")
BACKGROUND = re.compile(r"<p:bg>(.*?)</p:bg>", re.S)
CELL = re.compile(r"<a:tc[ >](.*?)</a:tc>", re.S)
CELL_PROPERTIES = re.compile(r"<a:tcPr\b[^>]*>(.*?)</a:tcPr>", re.S)
RUN_PROPERTIES = re.compile(r"<a:rPr\b[^>]*/>|<a:rPr\b[^>]*>.*?</a:rPr>", re.S)
SIZE = re.compile(r'<a:rPr\b[^>]*\bsz="(\d+)"')
BOLD = re.compile(r'<a:rPr\b[^>]*\bb="1"')

UNKNOWN = "?"  # 地が在るが色を決められない (= その下は探さない)


def _fill(properties: str, palette: Palette) -> str | None:
    """A shape's own ground: its colour, UNKNOWN when it cannot be told, None when it has none."""
    body = OUTLINE.sub("", properties)  # 線の色は地ではない
    if UNREADABLE.search(body):
        return UNKNOWN
    if "<a:solidFill>" in body:
        return solid(body, palette) or UNKNOWN
    return None


def _background(page: BuiltSlide, palette: Palette) -> str | None:
    for xml in (page.xml, *page.under):
        found = BACKGROUND.search(xml)
        if found:
            body = found.group(1)
            if UNREADABLE.search(body):
                return None
            if "<a:solidFill>" in body:
                return solid(body, palette)
            # 背景をテーマの塗りの番号で指す形 (= `<p:bgRef idx="1001"><a:schemeClr val="bg1"/>`)。
            # 中の色をそのまま地とみなす (= 番号が指す塗りが単色の時と同じ)
            reference = re.search(r"<p:bgRef\b[^>]*>(.*?)</p:bgRef>", body, re.S)
            return solid(f"<a:solidFill>{reference.group(1)}</a:solidFill>", palette) if reference else None
    return None


def _ground(shape: Shape, below: list[Shape], page: BuiltSlide, palette: Palette) -> str | None:
    properties = SHAPE_PROPERTIES.search(shape.xml)
    own = _fill(properties.group(1), palette) if properties else None
    if own:
        return None if own == UNKNOWN else own
    middle_x, middle_y = shape.left + shape.width // 2, shape.top + shape.height // 2
    for under in reversed(below):  # 上に描かれた物から
        if not (under.left <= middle_x <= under.right and under.top <= middle_y <= under.bottom):
            continue
        if under.kind == "pic":
            return None  # 絵の上の字は、絵のどこに乗るかで決まる
        properties = SHAPE_PROPERTIES.search(under.xml)
        fill = _fill(properties.group(1), palette) if properties else None
        if fill:
            return None if fill == UNKNOWN else fill
    return _background(page, palette)


def _runs(xml: str, palette: Palette):
    """(words, colour, the floor its size asks for) for each run whose colour is written."""
    for run in RUN.findall(xml):
        words = html.unescape("".join(TEXT.findall(run))).strip()
        properties = RUN_PROPERTIES.search(run)
        if not words or not properties:
            continue
        colour = solid(properties.group(0), palette)
        if not colour:
            continue
        size = SIZE.search(properties.group(0))
        points = int(size.group(1)) / 100 if size else None
        yield words, colour, reading_floor(points, bool(BOLD.search(properties.group(0))))


def _palette(deck: Path) -> Palette:
    with zipfile.ZipFile(deck) as archive:
        names = archive.namelist()
        theme = next((n for n in sorted(names) if re.fullmatch(r"ppt/theme/theme\d+\.xml", n)), None)
        master = next((n for n in sorted(names) if re.fullmatch(r"ppt/slideMasters/slideMaster\d+\.xml", n)), None)
        return Palette(archive.read(theme).decode("utf-8") if theme else "",
                       archive.read(master).decode("utf-8") if master else "")


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    allowed = set(allowed_pairs(config or {}))
    if (config or {}).get(NAME, True) is False:
        return Findings()
    palette = _palette(Path(deck))
    findings: list[Finding] = []
    #: 通した組ごとに、通した所 (= 頁と図形・セル) と明暗差
    passed: dict[tuple[str, str], tuple[set, float]] = {}

    def judge(page: int, words: str, colour: str, floor: float, ground: str, place) -> bool:
        ratio = contrast(colour, ground)
        if ratio < floor and (colour, ground) in allowed:
            passed.setdefault((colour, ground), (set(), ratio))[0].add((page, place))
            return False
        if ratio < floor:
            findings.append(Finding(
                NAME, page, f"{words[:40]!r} #{colour} on #{ground}",
                f"contrast {ratio:.1f}, below {floor:g} — it fades into its ground when presented"))
            return True
        return False

    for page in read(deck):
        shapes = page.shapes()
        for index, shape in enumerate(shapes):
            if shape.kind == "graphicFrame":
                for number, cell in enumerate(CELL.findall(shape.xml)):
                    properties = CELL_PROPERTIES.search(cell)
                    ground = _fill(properties.group(1), palette) if properties else None
                    if not ground or ground == UNKNOWN:
                        continue
                    if any(judge(page.number, *found, ground, (index, number)) for found in _runs(cell, palette)):
                        continue
                continue
            if shape.kind != "sp":
                continue
            ground = None
            for words, colour, floor in _runs(shape.xml, palette):
                ground = ground or _ground(shape, shapes[:index], page, palette)
                if not ground:
                    break
                if judge(page.number, words, colour, floor, ground, index):
                    break  # 1 つの図形は 1 度だけ言う
    return Findings(findings, [
        (NAME, f"#{colour} on #{ground} (contrast {ratio:.1f}): {len(places)} "
               f"{'place' if len(places) == 1 else 'places'} on {_pages(places)} — let through by [checks] {ALLOWED}")
        for (colour, ground), (places, ratio) in sorted(passed.items())])


def _pages(places: set) -> str:
    pages = sorted({page for page, _ in places})
    return ("page " if len(pages) == 1 else "pages ") + ", ".join(str(page) for page in pages)
