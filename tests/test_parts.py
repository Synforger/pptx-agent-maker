"""The part-level comparison: it must not drop anything it was not told to drop."""

from __future__ import annotations

import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from pptx_agent_maker.review import compare_parts, render_parts
from pptx_agent_maker.review import parts as parts_module

SLIDE = ('<p:sld><p:cSld><p:spTree>'
         '<p:sp><p:nvSpPr><p:cNvPr id="{id}" name="titlebar{id}"/></p:nvSpPr>'
         '<p:txBody><a:p><a:r><a:rPr sz="2000"{dirty}/><a:t>{text}</a:t></a:r></a:p></p:txBody>'
         '</p:sp></p:spTree></p:cSld></p:sld>')


def deck(where: Path, **members: bytes | str) -> Path:
    """A zip shaped like a package — the comparison only needs the entries."""
    where.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(where, "w") as archive:
        for name, body in members.items():
            archive.writestr(name.replace("__", "/"),
                             body if isinstance(body, bytes) else body.encode("utf-8"))
    return where


class PartsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _pair(self, left: dict, right: dict):
        return (deck(self.root / "a.pptx", **left), deck(self.root / "b.pptx", **right))

    def test_two_identical_decks_report_nothing(self):
        body = {"ppt__slides__slide1.xml": SLIDE.format(id=1, dirty="", text="hello")}
        a, b = self._pair(body, dict(body))
        found = compare_parts(a, b)
        self.assertEqual(found.changed, 0)
        self.assertIn("byte-identical", render_parts(found))

    def test_a_changed_slide_is_reported_with_its_words(self):
        a, b = self._pair(
            {"ppt__slides__slide1.xml": SLIDE.format(id=1, dirty="", text="before")},
            {"ppt__slides__slide1.xml": SLIDE.format(id=1, dirty="", text="after")})
        found = compare_parts(a, b)
        self.assertEqual([p.status for p in found.parts], ["changed"])
        body, _ = found.parts[0].diff()
        self.assertIn("before", body)
        self.assertIn("after", body)

    def test_an_added_image_is_reported_with_its_size(self):
        a, b = self._pair({"ppt__slides__slide1.xml": "<x/>"},
                          {"ppt__slides__slide1.xml": "<x/>",
                           "ppt__media__image1.png": b"\x89PNG" + b"0" * 500})
        found = compare_parts(a, b)
        self.assertEqual([p.status for p in found.parts], ["added"])
        self.assertIn("504 bytes", found.parts[0].headline())

    def test_a_removed_part_is_reported(self):
        a, b = self._pair({"ppt__slides__slide1.xml": "<x/>",
                           "ppt__notesSlides__notesSlide1.xml": "<n/>"},
                          {"ppt__slides__slide1.xml": "<x/>"})
        found = compare_parts(a, b)
        self.assertEqual([p.status for p in found.parts], ["removed"])
        self.assertIn("notesSlide1", found.parts[0].name)

    def test_the_editing_timestamp_alone_is_not_a_change(self):
        """docProps and viewProps move on every save and say nothing about the deck."""
        a, b = self._pair({"ppt__slides__slide1.xml": "<x/>", "docProps__core.xml": "<t>1</t>",
                           "ppt__viewProps.xml": "<v>1</v>"},
                          {"ppt__slides__slide1.xml": "<x/>", "docProps__core.xml": "<t>2</t>",
                           "ppt__viewProps.xml": "<v>2</v>"})
        found = compare_parts(a, b)
        self.assertEqual(found.changed, 0)
        self.assertEqual(len(found.ignored), 2, "docProps/core.xml and ppt/viewProps.xml")

    def test_dropping_the_noise_list_makes_the_timestamp_show_up(self):
        """Proof the exclusion is what keeps it quiet, not an accident of the fixture."""
        a, b = self._pair({"docProps__core.xml": "<t>1</t>"}, {"docProps__core.xml": "<t>2</t>"})
        original = parts_module.NOISE
        parts_module.NOISE = ()
        try:
            self.assertEqual(compare_parts(a, b).changed, 1)
        finally:
            parts_module.NOISE = original
        self.assertEqual(compare_parts(a, b).changed, 0)

    def test_powerpoints_own_churn_is_folded_and_counted(self):
        """A slide whose only difference is the spell-check mark and a renumbered id."""
        a, b = self._pair(
            {"ppt__slides__slide1.xml": SLIDE.format(id=393, dirty="", text="same")},
            {"ppt__slides__slide1.xml": SLIDE.format(id=381, dirty=' dirty="0"', text="same")})
        found = compare_parts(a, b)
        self.assertEqual(found.changed, 1, "the bytes do differ, so the part is still listed")
        body, folded = found.parts[0].diff()
        self.assertEqual(body, "", "nothing real changed, so no diff body")
        self.assertGreater(folded, 0)

    def test_a_real_change_survives_the_folding(self):
        a, b = self._pair(
            {"ppt__slides__slide1.xml": SLIDE.format(id=393, dirty="", text="before")},
            {"ppt__slides__slide1.xml": SLIDE.format(id=381, dirty=' dirty="0"', text="after")})
        body, folded = compare_parts(a, b).parts[0].diff()
        self.assertIn("after", body)
        self.assertGreater(folded, 0, "the churn around it is still folded")

    def test_raw_keeps_everything(self):
        a, b = self._pair(
            {"ppt__slides__slide1.xml": SLIDE.format(id=393, dirty="", text="same")},
            {"ppt__slides__slide1.xml": SLIDE.format(id=381, dirty=' dirty="0"', text="same")})
        body, folded = compare_parts(a, b).parts[0].diff(fold_churn=False)
        self.assertIn("titlebar393", body)
        self.assertEqual(folded, 0)


if __name__ == "__main__":
    unittest.main()
