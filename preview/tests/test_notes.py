"""発表者ノートの抽出を固定する。

.pptx を最小構成で組み立てて読ませる。要点は「ノートの無いスライドがあっても
頁とノートの対応がずれない」こと — notesSlideN.xml の番号は頁番号ではない。
"""

from __future__ import annotations

import zipfile

from pptx_live_preview import notes

_PRES = """<?xml version="1.0"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst>{ids}</p:sldIdLst>
</p:presentation>"""

_RELS = """<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{rows}
</Relationships>"""

_SLIDE_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
_NOTES_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"

_NOTES_XML = """<?xml version="1.0"?>
<p:notes xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
         xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld><p:spTree>
    <p:sp>
      <p:nvSpPr><p:nvPr><p:ph type="sldNum"/></p:nvPr></p:nvSpPr>
      <p:txBody><a:p><a:r><a:t>7</a:t></a:r></a:p></p:txBody>
    </p:sp>
    <p:sp>
      <p:nvSpPr><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr>
      <p:txBody>{paras}</p:txBody>
    </p:sp>
  </p:spTree></p:cSld>
</p:notes>"""


def _paras(lines):
    return "".join(
        f"<a:p><a:r><a:t>{line}</a:t></a:r></a:p>" for line in lines
    )


def build_deck(path, slides):
    """slides = [note text or None] — None のスライドはノート部品を持たない。"""
    with zipfile.ZipFile(path, "w") as zf:
        ids = "".join(
            f'<p:sldId id="{256 + i}" r:id="rId{i + 1}"/>' for i in range(len(slides))
        )
        zf.writestr("ppt/presentation.xml", _PRES.format(ids=ids))

        rows = "".join(
            f'<Relationship Id="rId{i + 1}" Type="{_SLIDE_TYPE}" '
            f'Target="slides/slide{i + 1}.xml"/>'
            for i in range(len(slides))
        )
        zf.writestr("ppt/_rels/presentation.xml.rels", _RELS.format(rows=rows))

        notes_no = 0
        for i, note in enumerate(slides, start=1):
            zf.writestr(f"ppt/slides/slide{i}.xml", "<p:sld/>")
            if note is None:
                zf.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", _RELS.format(rows=""))
                continue
            notes_no += 1
            row = (f'<Relationship Id="rId1" Type="{_NOTES_TYPE}" '
                   f'Target="../notesSlides/notesSlide{notes_no}.xml"/>')
            zf.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", _RELS.format(rows=row))
            zf.writestr(
                f"ppt/notesSlides/notesSlide{notes_no}.xml",
                _NOTES_XML.format(paras=_paras(note.split("\n"))),
            )
    return path


def test_notes_follow_slide_order(tmp_path):
    deck = build_deck(tmp_path / "w.pptx", ["first note", "second note"])
    assert notes.extract(deck) == ["first note", "second note"]


def test_missing_notes_keep_the_alignment(tmp_path):
    """ノートの無いスライドがあっても後続がずれない。"""
    deck = build_deck(tmp_path / "w.pptx", [None, "note on page two", None, "page four"])
    assert notes.extract(deck) == ["", "note on page two", "", "page four"]


def test_slide_number_placeholder_is_not_a_note(tmp_path):
    """ノート面のスライド番号はノート本文ではない。"""
    deck = build_deck(tmp_path / "w.pptx", ["real note"])
    assert notes.extract(deck) == ["real note"]


def test_multi_line_notes_survive(tmp_path):
    deck = build_deck(tmp_path / "w.pptx", ["line one\nline two"])
    assert notes.extract(deck) == ["line one\nline two"]


def test_unreadable_deck_is_empty_not_fatal(tmp_path):
    """壊れた .pptx でもプレビュー全体を止めない。"""
    broken = tmp_path / "broken.pptx"
    broken.write_bytes(b"not a zip")
    assert notes.extract(broken) == []


def test_deck_without_presentation_part_is_empty(tmp_path):
    empty = tmp_path / "empty.pptx"
    with zipfile.ZipFile(empty, "w") as zf:
        zf.writestr("docProps/app.xml", "<x/>")
    assert notes.extract(empty) == []
