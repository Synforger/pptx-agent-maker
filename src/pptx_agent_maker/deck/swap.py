"""New pictures and numbers on a page someone already arranged by hand.

輸入した頁は、人が PowerPoint で整えた形をそのまま持ってくる。文言は `replace` で
差し替えられたが、**絵と表の中身は入れ替えられなかった** ― 形は同じで中身だけが新しい頁を
作るには、毎回 PowerPoint で貼り直すか、頁を組み直すしかなかった。

絵と表は**頁の上の並び順**で指す (= 上の段から、同じ段は左から)。図形の名前で指す形は
確実だが、PowerPoint で名前を付ける手間が毎回かかる。並び順は `show <deck>:<page>` が
出すので、書く前に確かめられる。

⚠ **数が合わなければ止める。**頁に絵が 3 枚あるのに 2 枚渡されたとき、どれを残すかを
推測すると、古い絵が 1 枚だけ混ざった頁が焼ける。
⚠ **絵は枠に収め、縦横比を保つ。**枠は元の絵に合わせて引かれているので、比の違う絵を
そのまま流し込むと潰れる。枠の中央に、枠をはみ出さない最大の大きさで置く。元の切り抜きは
新しい絵には意味が無いので外す。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from ..write import aspect

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
EMBED = f"{{{NS['r']}}}embed"

#: 案件の素材として受け取る絵の種類 (= 手元の file には種類の登録が無いので、拡張子で決める)
IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
               "gif": "image/gif", "bmp": "image/bmp", "tif": "image/tiff",
               "tiff": "image/tiff"}


class SwapError(ValueError):
    """What was asked for does not match what is on the page."""


@dataclass(frozen=True)
class Box:
    """Where something sits on the page, in EMU."""

    x: int
    y: int
    cx: int
    cy: int


def reading_order(items: list[tuple[Box, object]]) -> list[object]:
    """Top to bottom, and left to right within a row.

    ⚠ **段は「上端が前の段の中ほどより上か」で決める。**上端の値だけで並べると、横に並べた
    つもりの 2 枚が 0.3mm ずれていただけで上下の順になる。
    """
    ordered = sorted(items, key=lambda item: (item[0].y, item[0].x))
    rows: list[list[tuple[Box, object]]] = []
    for box, thing in ordered:
        if rows:
            first = rows[-1][0][0]
            if box.y < first.y + first.cy / 2:
                rows[-1].append((box, thing))
                continue
        rows.append([(box, thing)])
    return [thing for row in rows for _box, thing in sorted(row, key=lambda item: item[0].x)]


def _box(xfrm) -> Box | None:
    """The position an `xfrm` gives (= its own `a:off` / `a:ext`, never a descendant's).

    ⚠ **子孫から探さない。**絵の中の拡張情報 (`<a:extLst><a:ext uri=...>`) も `a:ext` という
    名前で、先に現れる。実物のデッキで、そちらを位置と読んで落ちた。
    """
    if xfrm is None:
        return None
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None or ext is None:
        return None
    return Box(int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy")))


def pictures(tree) -> list:
    """The `<p:pic>` elements carrying an embedded picture, in reading order."""
    found = [(box, pic) for pic in tree.iter(f"{{{NS['p']}}}pic")
             if pic.find(".//a:blip", NS) is not None
             and (box := _box(pic.find("p:spPr/a:xfrm", NS))) is not None]
    return reading_order(found)


def tables(tree) -> list:
    """The `<a:tbl>` elements, in reading order of the frames holding them."""
    found = []
    for frame in tree.iter(f"{{{NS['p']}}}graphicFrame"):
        table = frame.find(".//a:tbl", NS)
        box = _box(frame.find("p:xfrm", NS))
        if table is not None and box is not None:
            found.append((box, table))
    return reading_order(found)


def grid(table) -> list[list[str]]:
    """A table's cells as text (= what `tables` would have to match)."""
    return [["".join(t.text or "" for t in cell.iter(f"{{{NS['a']}}}t"))
             for cell in row.findall("a:tc", NS)]
            for row in table.findall("a:tr", NS)]


def describe(deck: Path, page_number: int) -> str:
    """What `pictures` and `tables` would be matched against on one page, in order."""
    import zipfile

    from .archive import Archive

    order = Archive(deck.parent).order_of(deck)
    if not 1 <= page_number <= len(order):
        raise SwapError(f"{deck.name} has {len(order)} pages; asked for {page_number}")
    with zipfile.ZipFile(deck) as archive:
        slide = order[page_number - 1]
        tree = etree.fromstring(archive.read(f"ppt/slides/{slide}"))
        rels = etree.fromstring(archive.read(f"ppt/slides/_rels/{slide}.rels"))
    target = {rel.get("Id"): rel.get("Target", "").rsplit("/", 1)[-1] for rel in rels}
    cm = 360000
    lines = [f"{deck.name} page {page_number}"]
    found = pictures(tree)
    lines.append(f"  pictures ({len(found)}, in the order `pictures` fills them):")
    for number, pic in enumerate(found, start=1):
        box = _box(pic.find("p:spPr/a:xfrm", NS))
        name = pic.find("p:nvPicPr/p:cNvPr", NS)
        lines.append(f"    {number}. {box.cx / cm:.1f} x {box.cy / cm:.1f} cm at "
                     f"({box.x / cm:.1f}, {box.y / cm:.1f})  now {target.get(pic.find('.//a:blip', NS).get(EMBED), '?')}"
                     f"  \"{name.get('name') if name is not None else ''}\"")
    found = tables(tree)
    lines.append(f"  tables ({len(found)}, in the order `tables` fills them):")
    for number, table in enumerate(found, start=1):
        cells = grid(table)
        lines.append(f"    {number}. {len(cells)} rows x {[len(row) for row in cells]} cells; "
                     f"first row: {' | '.join(cells[0]) if cells else ''}")
    return "\n".join(lines)


# -- the swaps -------------------------------------------------------------


def swap_pictures(archive, slide: str, files: list[Path]) -> None:
    """Put `files` into the page's pictures, in reading order."""
    path = archive.slide(slide)
    tree = etree.parse(str(path))
    found = pictures(tree)
    if len(found) != len(files):
        raise SwapError(
            f"the page has {len(found)} pictures and {len(files)} were given — give one per "
            "picture, in reading order (`show <deck>:<page>` lists them)"
        )
    rels_path = archive.rels_of(slide)
    rels = etree.parse(str(rels_path))
    used = [int(r.get("Id")[3:]) for r in rels.getroot() if r.get("Id", "").startswith("rId")
            and r.get("Id")[3:].isdigit()]
    next_id = max(used, default=0) + 1
    replaced: set[str] = set()
    for pic, source in zip(found, files):
        extension = source.suffix.lower().lstrip(".")
        if extension not in IMAGE_TYPES:
            raise SwapError(f"{source.name}: pictures must be one of {', '.join(sorted(IMAGE_TYPES))}")
        name = archive.next_media_name(extension)
        (archive.tree / "ppt/media" / name).write_bytes(source.read_bytes())
        archive.register_media(name, IMAGE_TYPES[extension])
        rid = f"rId{next_id}"
        next_id += 1
        etree.SubElement(rels.getroot(), f"{{{NS['rel']}}}Relationship",
                         Id=rid, Type=IMAGE_REL, Target=f"../media/{name}")
        blip = pic.find(".//a:blip", NS)
        replaced.add(blip.get(EMBED))
        blip.set(EMBED, rid)
        for crop in pic.findall(".//a:srcRect", NS):
            crop.getparent().remove(crop)
        _fit(pic, aspect(source))

    # 使われなくなった関係を外す (= 残すと、載せないと決めた絵が file の中を運ばれる)
    text = etree.tostring(tree).decode("utf-8")
    for rel in list(rels.getroot()):
        if rel.get("Id") in replaced and f'"{rel.get("Id")}"' not in text:
            rels.getroot().remove(rel)
    tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)
    rels.write(str(rels_path), xml_declaration=True, encoding="UTF-8", standalone=True)


def _fit(pic, ratio: float) -> None:
    """Keep the picture inside its box, centred, at its own aspect ratio."""
    off = pic.find("p:spPr/a:xfrm/a:off", NS)
    ext = pic.find("p:spPr/a:xfrm/a:ext", NS)
    if off is None or ext is None:
        return  # 位置をレイアウトから継ぐ絵 (= 枠が頁に無い) は触らない
    x, y, cx, cy = (int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy")))
    if cx / cy > ratio:  # 枠のほうが横長 → 高さで決める
        width, height = round(cy * ratio), cy
    else:
        width, height = cx, round(cx / ratio)
    off.set("x", str(x + (cx - width) // 2))
    off.set("y", str(y + (cy - height) // 2))
    ext.set("cx", str(width))
    ext.set("cy", str(height))


def swap_tables(slide: Path, grids: list[list[list]]) -> None:
    """Put `grids` into the page's tables, in reading order, cell for cell.

    ⚠ **行と列の数が元と違えば止める。**表の枠は人が引いた幅と高さで、行を足すと頁から
    溢れ、減らすと空白が残る。形の違う表は、形の違う頁。
    結合の続きのセル (= 左や上のセルに飲まれた側) は画面に出ないので、そこは空で渡す。
    """
    tree = etree.parse(str(slide))
    found = tables(tree)
    if len(found) != len(grids):
        raise SwapError(
            f"the page has {len(found)} tables and {len(grids)} were given — give one per "
            "table, in reading order (`show <deck>:<page>` lists them)"
        )
    for number, (table, rows) in enumerate(zip(found, grids), start=1):
        cells = [row.findall("a:tc", NS) for row in table.findall("a:tr", NS)]
        shape = [len(row) for row in cells]
        given = [len(row) for row in rows]
        if shape != given:
            raise SwapError(
                f"table {number} is {len(shape)} rows of {shape} cells, and the one given is "
                f"{len(given)} rows of {given} — a table of another shape is another page"
            )
        for tr, values in zip(cells, rows):
            for cell, value in zip(tr, values):
                value = "" if value is None else str(value)
                if cell.get("hMerge") == "1" or cell.get("vMerge") == "1":
                    if value:
                        raise SwapError(
                            f"table {number}: {value!r} was given for a cell merged into its "
                            "neighbour — it does not show; give \"\" there"
                        )
                    continue
                _set_text(cell, value)
    tree.write(str(slide), xml_declaration=True, encoding="UTF-8", standalone=True)


def _set_text(cell, value: str) -> None:
    """Replace a cell's words, keeping how the first of them was set."""
    body = cell.find("a:txBody", NS)
    paragraphs = body.findall("a:p", NS)
    first = paragraphs[0] if paragraphs else None
    ppr = first.find("a:pPr", NS) if first is not None else None
    rpr = None
    if first is not None:
        run = first.find("a:r", NS)
        rpr = run.find("a:rPr", NS) if run is not None else first.find("a:endParaRPr", NS)
    for paragraph in paragraphs:
        body.remove(paragraph)
    for line in value.split("\n"):
        p = etree.SubElement(body, f"{{{NS['a']}}}p")
        if ppr is not None:
            p.append(_copy(ppr))
        if line:
            r = etree.SubElement(p, f"{{{NS['a']}}}r")
            if rpr is not None:
                r.append(_copy(rpr, tag="rPr"))
            etree.SubElement(r, f"{{{NS['a']}}}t").text = line
        elif rpr is not None:
            p.append(_copy(rpr, tag="endParaRPr"))


def _copy(element, tag: str | None = None):
    clone = etree.fromstring(etree.tostring(element))
    if tag:
        clone.tag = f"{{{NS['a']}}}{tag}"
    return clone
