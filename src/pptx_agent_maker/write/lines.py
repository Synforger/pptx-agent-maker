"""Write a line as a connector: straight, bent at right angles, or hopping over the lines it crosses.

誰が呼ぶか: `pptx.add_page` (= 頁の `Line` を 1 本ずつ)。線の形だけを知り、頁の他の物は知らない。

* 真っすぐな線は、まっすぐなコネクタ
* 曲がる線 (= 曲がり角 1〜4 つ) は、PowerPoint の曲がるコネクタ (= `bentConnector2`〜`bentConnector5`)。曲がり角の
  位置は調整値 (`adj`) で持つので、人が箱を動かしても 1 つの図形のまま
* ほかの線を跳び越す線は、図形の線 (= `custGeom`)。半円の跳び越しはプリセットに無いので、点の並びと半円で
  描く。この線は箱を動かしても付いて来ない
"""

from __future__ import annotations

import math

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu

from ..layout.parts.elements import Line
from ..layout.tokens import Theme

Point = tuple[int, int]

#: プリセットの曲がるコネクタで書く曲がり角の数の上限。曲がり角 3 つ以上のプリセット (= `bentConnector4`・
#: `bentConnector5`) は、LibreOffice が調整値を読まずに自分の道へ引き直し (= 描いた絵の折れ目が計算と合わない)、
#: これで見せる道具のプレビューが嘘になる。それ以上は図形の線で書く。LibreOffice が調整値どおりに描くように
#: なったら、ここを 4 に上げる
PRESET_BENDS = 2
#: 曲がるコネクタの調整値の単位 (= 枠の幅か高さに対する 10 万分率)
ADJ_UNIT = 100000
#: 辺の番号 (= 0 右・1 下・2 左・3 上) → 矩形の接続点の番号 (= 0 上・1 左・2 下・3 右)
SITES = (3, 2, 1, 0)
#: 接続を付ける箱の形
BOXES = (MSO_SHAPE.RECTANGLE, MSO_SHAPE.ROUNDED_RECTANGLE)
#: DrawingML の角度の単位 (= 1 度の 6 万分の 1)
DEGREE = 60000


def write_line(slide, element: Line, theme: Theme):
    """A connector between two points, straight, bent or hopping, its arrowhead (if any) at the end.

    矢じりは線の書式 (= `a:tailEnd`) で付ける。並びは決まっている (= 塗り・破線の後に端) ― 順を違えた file を
    PowerPoint は修復しようとする。
    """
    points = element.points()
    fitted = None if element.hops else _bent_connector(points) if element.corners else None
    if element.hops or (element.corners and fitted is None):
        shape = _freeform(slide, points, element.hop_points(), element.hop)
        reversed_path = False
    else:
        reversed_path = fitted is not None and fitted["reversed"]
        begin, end = (points[-1], points[0]) if reversed_path else (points[0], points[-1])
        shape = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Emu(begin[0]), Emu(begin[1]), Emu(end[0]), Emu(end[1]))
        if fitted is not None:
            _set_bent(shape, fitted)
            _join(slide, shape, *((element.ends_on, element.begins_on) if reversed_path else (element.begins_on, element.ends_on)))
    style = shape._element.find(qn("p:style"))
    if style is not None:                      # テーマの線の書式を引かない (= `_plain` と同じ理由)
        shape._element.remove(style)
    shape.line.color.rgb = RGBColor.from_string(element.colour)
    shape.line.width = Emu(theme.spacing.hairline * 3 // 2)
    if element.arrow:
        line = shape.line._get_or_add_ln()
        line.append(line.makeelement(qn("a:headEnd" if reversed_path else "a:tailEnd"),
                                     {"type": "triangle", "w": "med", "len": "med"}))
    return shape


# -- 曲がるコネクタ ----------------------------------------------------------


def _bent_connector(points: list[Point]) -> dict | None:
    """How to write a bent line as one preset connector, or None when no preset draws it.

    プリセットの道は、枠の左上から右へ進み、曲がり角ごとに縦と横を交互に進んで、右下に着く (= 曲がり角が 1 つ
    なら右の辺で下へ、2 つなら真ん中で縦に渡って右へ、…)。反転と回転でほかの向きを書く。**回転は 0 度と 180 度だけ**
    (= 90 度の回転は、LibreOffice が曲がり方を読み違える)。左右の反転も使わない (= 左右反転した曲がるコネクタは、
    LibreOffice が折れ目を逆の角に描く)。始まりと終わりを入れ替えた道も試す (= 縦に出る線を横から書く)。

    縦に出て縦に入る線 (= 曲がり角 2 つ) は、`PRESET_BENDS` が 4 以上なら、長さ 0 の横の区間を両端に足した
    4 つの曲がり角の道として書く (= `bentConnector5` の最初と最後の調整値を 0 と 100%)。
    `PRESET_BENDS` を超える曲がり角の線と、横に出て縦へ曲がる 2 つ目が書けない線は、None (= 図形の線で書く)。
    """
    if len(points) - 2 > PRESET_BENDS:
        return None
    paths = [points]
    if len(points) == 4 and PRESET_BENDS >= 4:
        paths.append([points[0], *points, points[-1]])
    for path in paths:
        for reverse in (False, True):
            for rot in (0, 180):
                for flip in (False, True):
                    found = _fit(path[::-1] if reverse else path, rot, flip)
                    if found is not None:
                        return {"reversed": reverse, "rot": rot, "flip": flip, **found}
    return None


def _fit(path: list[Point], rot: int, flip: bool) -> dict | None:
    """The frame and the adjustments that make the preset draw `path` under this rotation and flip, or None if it cannot."""
    (sx, sy), (ex, ey) = path[0], path[-1]
    across, down = abs(ex - sx), abs(ey - sy)
    wide, tall = across, down
    centre = ((sx + ex) / 2, (sy + ey) / 2)
    local = [_local(point, centre, wide, tall, rot, flip) for point in path]
    if not (_near(local[0], (0, 0)) and _near(local[-1], (wide, tall))):
        return None
    adjustments = _adjustments(local, wide, tall)
    if adjustments is None:
        return None
    return {"frame": ((min(sx, ex), min(sy, ey)), (wide, tall)), "adjustments": adjustments}


def _local(point: Point, centre: tuple[float, float], wide: int, tall: int, rot: int, flip: bool) -> tuple[float, float]:
    """Where a point of the slide falls in the preset's own frame (= the frame's top left is (0, 0)), undoing the rotation and the flip."""
    ux, uy = point[0] - centre[0], point[1] - centre[1]
    turn = math.radians(rot)
    cos, sin = round(math.cos(turn)), round(math.sin(turn))
    ux, uy = ux * cos + uy * sin, -ux * sin + uy * cos
    if flip:
        uy = -uy
    return ux + wide / 2, uy + tall / 2


def _near(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1


def _adjustments(local: list[tuple[float, float]], wide: int, tall: int) -> list[int] | None:
    """The `adj` values of the preset that goes through these points (= none for a single bend), or None when the points do not fit its shape."""
    corners = local[1:-1]
    bends = len(corners)
    if bends == 1:
        return [] if _near(corners[0], (wide, 0)) else None
    if bends == 2:
        (x1, y1), (x2, y2) = corners
        fits = abs(y1) <= 1 and abs(x2 - x1) <= 1 and abs(y2 - tall) <= 1
        return [_unit(x1, wide)] if fits and wide >= 1 else None
    if bends == 3:
        (x1, y1), (x2, y2), (x3, y3) = corners
        fits = abs(y1) <= 1 and abs(x2 - x1) <= 1 and abs(y3 - y2) <= 1 and abs(x3 - wide) <= 1
        return [_unit(x1, wide), _unit(y2, tall)] if fits and wide >= 1 and tall >= 1 else None
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = corners
    fits = abs(y1) <= 1 and abs(x2 - x1) <= 1 and abs(y3 - y2) <= 1 and abs(x4 - x3) <= 1 and abs(y4 - tall) <= 1
    return [_unit(x1, wide), _unit(y2, tall), _unit(x3, wide)] if fits and wide >= 1 and tall >= 1 else None


def _unit(position: float, extent: int) -> int:
    return round(position / extent * ADJ_UNIT)


def _set_bent(shape, fitted: dict) -> None:
    """Make a connector the preset bent one that `_bent_connector` fitted."""
    (left, top), (wide, tall) = fitted["frame"]
    geometry = shape._element.spPr.find(qn("a:prstGeom"))
    geometry.set("prst", f"bentConnector{len(fitted['adjustments']) + 2}")
    guides = geometry.find(qn("a:avLst"))
    for number, value in enumerate(fitted["adjustments"], start=1):
        guides.append(guides.makeelement(qn("a:gd"), {"name": f"adj{number}", "fmla": f"val {value}"}))
    frame = shape._element.spPr.find(qn("a:xfrm"))
    for name in ("rot", "flipH", "flipV"):
        frame.attrib.pop(name, None)
    frame.find(qn("a:off")).set("x", str(left))
    frame.find(qn("a:off")).set("y", str(top))
    frame.find(qn("a:ext")).set("cx", str(wide))
    frame.find(qn("a:ext")).set("cy", str(tall))
    if fitted["rot"]:
        frame.set("rot", str(fitted["rot"] * DEGREE))
    if fitted["flip"]:
        frame.set("flipV", "1")


def _join(slide, connector, begins_on, ends_on) -> None:
    """Attach the two ends of a connector to the boxes (= the shapes that stand exactly where the line's ends say), at the middle of the side.

    箱の図形が見つからない端は付けない (= 付ける先の無い接続は修復の種)。矩形と角丸の矩形の接続点は、上・左・下・右の順。
    """
    holder = connector._element.find(qn("p:nvCxnSpPr")).find(qn("p:cNvCxnSpPr"))
    for tag, joined in (("a:stCxn", begins_on), ("a:endCxn", ends_on)):
        found = _box_shape(slide, joined[0]) if joined else None
        if found is not None:
            holder.append(holder.makeelement(qn(tag), {"id": str(found.shape_id), "idx": str(SITES[joined[1]])}))


def _box_shape(slide, box):
    """The rectangle (or rounded rectangle) on the slide that stands exactly on `box`, if there is one."""
    for shape in slide.shapes:
        if (shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and shape.auto_shape_type in BOXES
                and (shape.left, shape.top, shape.width, shape.height) == (box.left, box.top, box.width, box.height)):
            return shape
    return None


# -- 跳び越す線 --------------------------------------------------------------


def _freeform(slide, points: list[Point], hops: list[Point], radius: int):
    """A free-form line through `points`, a half circle over each hop (above a sideways run, to the right of a downward one).

    ⚠ **コネクタ (= `p:cxnSp`) ではなく図形 (= `p:sp`) で書く。** LibreOffice はコネクタの図形の形を読まずに、
    自分の道へ引き直す (= 描いた絵の線が計算と合わない)。
    """
    steps = _steps(points, hops, radius)
    xs = [x for step in steps for x in step["xs"]]
    ys = [y for step in steps for y in step["ys"]]
    left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
    wide, tall = right - left, bottom - top
    commands = [f'<a:moveTo><a:pt x="{points[0][0] - left}" y="{points[0][1] - top}"/></a:moveTo>']
    for step in steps:
        commands.extend(step["commands"](left, top))
    path = (f'<a:custGeom {nsdecls("a")}><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/>'
            f'<a:rect l="0" t="0" r="r" b="b"/><a:pathLst><a:path w="{wide}" h="{tall}" fill="none">'
            f'{"".join(commands)}</a:path></a:pathLst></a:custGeom>')
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(left), Emu(top), Emu(wide), Emu(tall))
    properties = shape._element.spPr
    properties.replace(properties.find(qn("a:prstGeom")), parse_xml(path))
    shape.name = f"Freeform {shape.shape_id - 1}"
    shape.fill.background()
    shape.shadow.inherit = False
    return shape


def _steps(points: list[Point], hops: list[Point], radius: int) -> list[dict]:
    """Each run of the line as the commands that draw it (given the frame's corner) and the coordinates it reaches."""
    steps = []
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        sideways = y1 == y2
        direction = (1 if x2 > x1 else -1) if sideways else (1 if y2 > y1 else -1)
        here = sorted((hop for hop in hops if _on(hop, (x1, y1), (x2, y2))),
                      key=lambda hop: (hop[0] - x1) * direction if sideways else (hop[1] - y1) * direction)
        xs, ys = [x1, x2], [y1, y2]
        for hx, hy in here:
            xs.append(hx if sideways else hx + radius)
            ys.append(hy - radius if sideways else hy)
        steps.append({"xs": xs, "ys": ys, "commands": _commands((x1, y1), (x2, y2), here, radius, sideways, direction)})
    return steps


def _commands(begin: Point, end: Point, hops: list[Point], radius: int, sideways: bool, direction: int):
    """A function that gives the path commands of one run, once the frame's corner is known."""
    def draw(left: int, top: int) -> list[str]:
        out = []
        for hx, hy in hops:
            if sideways:
                before = (hx - direction * radius, hy)
                start, sweep = (180, 180) if direction > 0 else (0, -180)
            else:
                before = (hx, hy - direction * radius)
                start, sweep = (270, 180) if direction > 0 else (90, -180)
            out.append(f'<a:lnTo><a:pt x="{before[0] - left}" y="{before[1] - top}"/></a:lnTo>')
            out.append(f'<a:arcTo wR="{radius}" hR="{radius}" stAng="{start * DEGREE}" swAng="{sweep * DEGREE}"/>')
        out.append(f'<a:lnTo><a:pt x="{end[0] - left}" y="{end[1] - top}"/></a:lnTo>')
        return out
    return draw


def _on(point: Point, begin: Point, end: Point) -> bool:
    """Whether a point lies on the run from `begin` to `end`."""
    (x1, y1), (x2, y2) = begin, end
    return min(x1, x2) <= point[0] <= max(x1, x2) and min(y1, y2) <= point[1] <= max(y1, y2)
