"""The frame each declared picture is given: how large to draw it so it fills its place.

絵は縦横比を保って枠の中に置かれる (= 枠より縦長なら高さで、横長なら幅で決まり、残りは隙間になる)。
グラフを枠と同じ大きさ・同じ縦横比で描けば、絵は枠いっぱいに置かれ、字は描いた大きさのまま頁に載る。
枠は頁を組まないと決まらない (= 段の高さは、ほかの部品と絵の縦横比で割り振られる) ので、ここは build と
同じ道で宣言の頁を組み、焼かずに枠を読む。
"""

from __future__ import annotations

from ..layout.geometry import EMU_PER_INCH, Rect
from ..layout.parts.elements import Figure
from ..project.files.manifest import Manifest
from ..project.files.workspace import Workspace
from .build import declared_page, theme_of


def frames(workspace: Workspace, manifest: Manifest) -> list[dict]:
    """One entry per picture of a declared page: the page, the picture, its frame and where it is placed.

    複製と輸入の頁の絵は、テンプレートの絵の枠に差し替わるので、ここには出ない。同じ絵を 2 頁に置けば、
    頁ごとに 1 件ずつ出る。枠は今の絵で組んだ物 (= 絵を描き直して縦横比が変わる頁では、組み直すと枠も動く)。
    """
    theme = theme_of(workspace, manifest)
    found = []
    for index, entry in enumerate(manifest.entries, start=1):
        if entry.kind != "declare":
            continue
        page = declared_page(workspace, manifest, entry, index, theme)
        for element in page.build():
            if isinstance(element, Figure) and element.frame is not None:
                found.append({"page": index, "picture": element.source.name,
                              "frame": _size(element.frame), "placed": _size(element.rect)})
    return found


def _size(rect: Rect) -> dict:
    """A width and a height in EMU and in inches."""
    return {"width_emu": rect.width, "height_emu": rect.height,
            "width_in": round(rect.width / EMU_PER_INCH, 3), "height_in": round(rect.height / EMU_PER_INCH, 3)}
