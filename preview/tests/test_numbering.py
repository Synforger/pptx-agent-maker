"""Page numbers in the preview match PowerPoint when a deck starts counting elsewhere.

⚠ LibreOffice は presentation.xml の開始番号 (`firstSlideNum`) を読まない。表紙に番号を付けない
資料 (= 開始 0、表紙の次が 1) が、プレビューでだけ 2・3 と描かれた。
"""

from __future__ import annotations

import zipfile

from pptx import Presentation
from pptx.util import Inches
from lxml import etree

from pptx_live_preview.render import numbered_as_powerpoint

FIELD = ('<a:fld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
         'id="{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}" type="slidenum">'
         '<a:rPr lang="en-US" sz="1800"/><a:t>&lt;#&gt;</a:t></a:fld>')


def _deck(path, first: int | None):
    prs = Presentation()
    for _ in range(3):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        box = slide.shapes.add_textbox(Inches(8), Inches(6.5), Inches(1), Inches(0.5))
        box.text_frame.paragraphs[0]._p.append(etree.fromstring(FIELD))
    plain = path.with_suffix(".plain.pptx")
    prs.save(plain)
    with zipfile.ZipFile(plain) as source, zipfile.ZipFile(path, "w") as out:
        for item in source.infolist():
            data = source.read(item)
            if item.filename == "ppt/presentation.xml" and first is not None:
                data = data.replace(b"<p:presentation ", f'<p:presentation firstSlideNum="{first}" '.encode(), 1)
            out.writestr(item, data)
    return path


def _numbers(deck) -> list[str]:
    with zipfile.ZipFile(deck) as z:
        order = sorted((n for n in z.namelist() if n.startswith("ppt/slides/slide")),
                       key=lambda n: int(n.rsplit("slide", 1)[1].split(".")[0]))
        found = []
        for name in order:
            xml = z.read(name).decode()
            assert 'type="slidenum"' not in xml, "the field is left for LibreOffice to count"
            found.append(xml.split("<a:t>")[-1].split("</a:t>")[0])
        return found


def test_a_deck_that_starts_at_zero_is_numbered_as_powerpoint_numbers_it(tmp_path):
    deck = _deck(tmp_path / "w1.pptx", first=0)
    copy = numbered_as_powerpoint(deck, tmp_path / "work")
    assert copy != deck and copy.name == deck.name, "the pdf is named after the deck"
    assert _numbers(copy) == ["0", "1", "2"]
    with zipfile.ZipFile(copy) as z:
        assert 'sz="1800"' in z.read("ppt/slides/slide2.xml").decode(), "the number keeps its look"


def test_a_deck_that_starts_at_one_is_handed_over_as_it_is(tmp_path):
    for first in (None, 1):
        deck = _deck(tmp_path / f"w{first}.pptx", first=first)
        assert numbered_as_powerpoint(deck, tmp_path / "work") == deck
