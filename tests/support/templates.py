"""A template whose first layout is a page of content: a title placeholder in a colour, and a logo.

同梱の見本の 1 枚目のレイアウトは表紙 (= 真ん中の題)。案件のテンプレートは、1 枚目が本文の頁で、題の枠に
色が付き、隅にロゴが在ることが多い。その形を、同梱の見本のレイアウトを書き換えて作る (= 絵の file を
持たずに済むよう、ロゴは塗った矩形で置く。重なりの検査は絵と同じに数える)。
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.layout.base.geometry import Rect  # noqa: E402

SHIPPED = REPO / "src" / "pptx_agent_maker" / "templates" / "project" / "specimen.pptx"
LAYOUT = "ppt/slideLayouts/slideLayout1.xml"
#: 題の枠の字の色 (= テーマの色のどれでもない青。継いだことが色で分かる)
TITLE_COLOUR = "0070C0"


def a_template(destination: Path, *, title: bool = True, logo: Rect | None = None) -> Path:
    """The shipped specimen, with its first layout made a page of content."""
    with zipfile.ZipFile(SHIPPED) as source, zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as out:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == LAYOUT:
                xml = data.decode("utf-8")
                if title:
                    assert xml.count('<p:ph type="ctrTitle"/>') == 1
                    xml = xml.replace('<p:ph type="ctrTitle"/>', '<p:ph type="title"/>')
                    xml = xml.replace(
                        "<a:lstStyle/>",
                        '<a:lstStyle><a:lvl1pPr algn="ctr"><a:defRPr sz="2500" b="0"><a:solidFill>'
                        f'<a:srgbClr val="{TITLE_COLOUR}"/></a:solidFill></a:defRPr></a:lvl1pPr></a:lstStyle>', 1)
                if logo is not None:
                    xml = xml.replace("</p:spTree>", (
                        '<p:sp><p:nvSpPr><p:cNvPr id="90" name="Logo"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
                        f'<a:xfrm><a:off x="{logo.left}" y="{logo.top}"/><a:ext cx="{logo.width}" cy="{logo.height}"/>'
                        '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill>'
                        '<a:srgbClr val="7F7F7F"/></a:solidFill></p:spPr></p:sp></p:spTree>'))
                data = xml.encode("utf-8")
            out.writestr(item, data)
    return destination
