"""Pictures on a built page, with the image each one shows and how much of it is cropped.

絵の検査 (= 潰れ・引き伸ばし) は、頁の上の枠と、元の絵の画素の両方が要る。枠は頁の XML、画素は
部品の中の media に在るので、頁の関係 (= rels) をたどって結ぶ。

⚠ **元の大きさが読めない絵 (= SVG・EMF・WMF、壊れた file) は返さない。**測れない物を赤にしない。
"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .slide import Shape, read

EMBED = re.compile(r'<a:blip\b[^>]*\br:embed="([^"]+)"')
CROP = re.compile(r"<a:srcRect\b([^>]*)/>")
EDGE = re.compile(r'\b([ltrb])="(-?\d+)"')
RELATION = re.compile(r"<Relationship\b[^>]*>")
#: srcRect の値は 1/1000 % (= 100000 で全体)
WHOLE = 100000


@dataclass(frozen=True)
class Placed:
    """One picture as a page shows it."""

    page: int
    shape: Shape
    #: 元の絵の画素 (= 幅, 高さ)
    pixels: tuple[int, int]
    #: 切り抜いて残る割合 (= 幅, 高さ。切り抜かなければ 1)
    kept: tuple[float, float]

    @property
    def shown_pixels(self) -> tuple[float, float]:
        """The pixels that end up inside the frame."""
        return self.pixels[0] * self.kept[0], self.pixels[1] * self.kept[1]


def _targets(archive: zipfile.ZipFile, slide: str) -> dict[str, str]:
    try:
        rels = archive.read(f"ppt/slides/_rels/{slide}.rels").decode("utf-8")
    except KeyError:
        return {}
    found = {}
    for relation in RELATION.findall(rels):
        rid = re.search(r'\bId="([^"]+)"', relation)
        target = re.search(r'\bTarget="([^"]+)"', relation)
        if rid and target and 'TargetMode="External"' not in relation:
            found[rid.group(1)] = posixpath.normpath(posixpath.join("ppt/slides", target.group(1)))
    return found


def _kept(xml: str) -> tuple[float, float]:
    crop = CROP.search(xml)
    if not crop:
        return 1.0, 1.0
    edges = {side: int(value) for side, value in EDGE.findall(crop.group(1))}
    width = 1 - (edges.get("l", 0) + edges.get("r", 0)) / WHOLE
    height = 1 - (edges.get("t", 0) + edges.get("b", 0)) / WHOLE
    return width, height


def placed(deck: Path) -> list[Placed]:
    """Every picture on every page whose image size can be read."""
    found: list[Placed] = []
    sizes: dict[str, tuple[int, int] | None] = {}
    with zipfile.ZipFile(Path(deck)) as archive:
        for page in read(deck):
            targets = _targets(archive, page.name)
            for shape in page.shapes():
                if shape.kind != "pic":
                    continue
                embed = EMBED.search(shape.xml)
                media = targets.get(embed.group(1)) if embed else None
                if media is None:
                    continue
                if media not in sizes:
                    try:
                        with Image.open(io.BytesIO(archive.read(media))) as image:
                            sizes[media] = image.size
                    except (KeyError, OSError, UnidentifiedImageError):
                        sizes[media] = None
                kept = _kept(shape.xml)
                if sizes[media] and kept[0] > 0 and kept[1] > 0:
                    found.append(Placed(page.number, shape, sizes[media], kept))
    return found
