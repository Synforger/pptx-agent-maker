"""The albums the example collection is browsed with: one per deck under each scene, one per form.

見本の集まり (= `scripts/examples/fetch-examples.py`) は、プレビューで見る束も書く。場面の束は資料を
そのまま並べ、形の束は頁の文字の抜き出しを語で引いて集める。ここでは小さな集まりを tmp に作って、
束の中身 (= 絵の path と注記) と、語の引き方が拾う物・外す物を見る。
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location("fetch_examples", REPO / "scripts" / "examples" / "fetch-examples.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


examples = _script()


def _page(visual: str) -> str:
    return f"# Audit\n\n## 1. Textual Claims\n\n- **Title:** A page\n\n## 3. Visual Interpretation\n\n{visual}\n"


class Forms(unittest.TestCase):
    def test_a_form_is_picked_by_the_headings_of_what_the_page_shows(self):
        self.assertEqual(examples.form_of(_page("- **Venn Diagram**: three circles")), {"円の重なり": "venn diagram"})
        self.assertIn("地図", examples.form_of(_page("- **World Map with color-coded regions**: shading")))
        self.assertIn("輪の図", examples.form_of(_page("- **Circular Flow Diagram**: four stages")))
        self.assertIn("コードの枠", examples.form_of(_page("- **Code Block**: a function")))

    def test_what_only_resembles_a_form_is_left_out(self):
        for visual in ("- **Background world map**: faint", "- **World map icon**: small",
                       "- **Product roadmap**: a timeline", "- **QR code**: bottom right",
                       "- **Illustrated tree**: a forest scene", "- **Slide number**: 3"):
            self.assertEqual(examples.form_of(_page(visual)), {}, visual)

    def test_a_big_number_is_picked_from_the_words_since_it_has_no_heading_of_its_own(self):
        picked = examples.form_of(_page("- **Headline**: the figure is set in large purple numerals at the top"))
        self.assertEqual(picked, {"大きな数字": "large purple numerals"})

    def test_a_page_without_the_section_picks_nothing(self):
        self.assertEqual(examples.form_of("# Audit\n\n- **Venn Diagram**: but outside the section\n"), {})


class Albums(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.decks = []
        for scene, topic, title in (("work_report", "b-topic", "Same opening words, the second"),
                                    ("work_report", "a-topic", "Same opening words, the first"),
                                    ("business_plan", "c-topic", "")):
            deck = self.root / "slides-align" / scene / topic / "1-Tool"
            deck.mkdir(parents=True)
            for number in (1, 2):
                (deck / f"page-{number:02d}.jpg").write_bytes(b"jpeg")
                (deck / f"page-{number:02d}.md").write_text(
                    _page("- **Venn Diagram**: overlap" if number == 2 else "- **Photo**: a person"), encoding="utf-8")
            self.decks.append({"difficulty": scene, "topic": topic, "titles": [title] if title else [],
                               "path": str(deck.relative_to(self.root)), "pages": 2})
        self.decks.append({"difficulty": "brand_promote", "topic": "gone", "missing": True})

    def test_each_scene_gets_a_folder_and_each_deck_an_album_of_its_pages(self):
        offers = examples.albums(self.root, self.decks)
        self.assertEqual([name for name, _ in offers], ["見本 · 業務の報告", "見本 · 事業計画", "見本 · 頁の形"])
        work = self.root / "albums" / "scenes" / "work_report"
        names = sorted(p.name for p in work.glob("*.album"))
        # 同じ書き出しの題でも、番号で別の file になる (= 縮めた題だけの名前は上書きし合う)
        self.assertEqual(names, ["01-Same_opening_words_the_first.album", "02-Same_opening_words_the_second.album"])
        lines = (work / names[0]).read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "# 業務の報告 · Same opening words, the first · 01/02 頁")
        self.assertEqual(lines[1], "../../../slides-align/work_report/a-topic/1-Tool/page-01.jpg")
        self.assertTrue((work / lines[1]).is_file(), "the album points at the gathered picture, relative to itself")
        # 題の抜き出しが無い資料は、題材の名前で出す
        (plan,) = (self.root / "albums" / "scenes" / "business_plan").glob("*.album")
        self.assertEqual(plan.name, "01-c-topic.album")

    def test_a_form_album_gathers_the_pages_its_words_picked_with_where_they_came_from(self):
        examples.albums(self.root, self.decks)
        forms = self.root / "albums" / "forms"
        self.assertEqual([p.name for p in forms.glob("*.album")], ["円の重なり.album"])
        lines = (forms / "円の重なり.album").read_text(encoding="utf-8").splitlines()
        pictures = [line for line in lines if not line.startswith("#")]
        self.assertEqual(len(pictures), 3)
        self.assertTrue(all((forms / p).is_file() and p.endswith("page-02.jpg") for p in pictures))
        self.assertIn("# 拾った語: venn diagram", lines)

    def test_the_albums_are_written_afresh_each_time(self):
        examples.albums(self.root, self.decks)
        stale = self.root / "albums" / "scenes" / "work_report" / "99-old.album"
        stale.write_text("gone.jpg\n", encoding="utf-8")
        examples.albums(self.root, self.decks)
        self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
