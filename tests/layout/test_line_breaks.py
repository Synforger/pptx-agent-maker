"""A line break in a name is a line of its own wherever a name is written, not only in a bar.

⚠ 見張るのは 3 つ ― 線表の印・日付・期間の名前が、書かれた行の数ぶんの高さを取ること、吹き出しの
名前が行ごとの段落で書かれること、見本の全部の頁の全部の名前に改行を入れても、高さが足りない箱と
1 つの run に入った改行が出ないこと (= 手で通した洗い出しを機械に残した物)。
"""

from __future__ import annotations

import copy
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "scripts" / "check"))
from support.pages import named  # noqa: E402
from layout.test_compose import compose, kinds, row, voices  # noqa: E402
from layout.test_timeline import bar, lane, page  # noqa: E402
from layout.test_timeline_bars import baked, shape_of  # noqa: E402

import snapshot  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.parts.page import PageFullError  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Bar, Text  # noqa: E402
from pptx_agent_maker.layout.tokens import DEFAULT  # noqa: E402

TWO_LINES = "first\nsecond"


def reaches_below(built) -> int:
    """How far below the body of the page something stands (= 0 when everything is inside)."""
    return max(max(e.rect.bottom for e in built.build()) - built.theme.frame().bottom, 0)


def lines_of(built, text: str) -> float:
    """How many lines of its own size the element of this name is tall."""
    element = named(built, text)
    return element.rect.height / DEFAULT.line_height(element.size)


class ALineBreakInAMark(unittest.TestCase):
    """The name beside a mark of a lane."""

    def test_the_name_takes_a_line_for_each_line_written(self):
        built = page([lane("One", [bar(0, 6, "work")], marks=[{"at": 3, "text": TWO_LINES}])])
        label = named(built, TWO_LINES)
        self.assertEqual("label", label.kind)
        self.assertGreaterEqual(label.rect.height,
                                2 * DEFAULT.line_height(label.size) + 2 * DEFAULT.spacing.bar_pad_y)

    def test_a_row_of_marks_stands_as_tall_as_its_tallest_name(self):
        short = page([lane("One", marks=[{"at": 1, "text": "one"}])])
        tall = page([lane("One", marks=[{"at": 1, "text": TWO_LINES}])])
        self.assertGreater(named(tall, TWO_LINES).rect.height, named(short, "one").rect.height)

    def test_the_page_counts_the_lines_of_a_name_for_the_height_it_needs(self):
        built = page([lane(f"Lane {n}", marks=[{"at": 1, "text": TWO_LINES if n == 3 else "one"}])
                      for n in range(6)])
        self.assertEqual(0, reaches_below(built))

    def test_a_name_stands_one_line_taller_than_a_name_of_one_line_beside_it(self):
        built = page([lane("One", marks=[{"at": 1, "text": "one"}]), lane("Two", marks=[{"at": 1, "text": TWO_LINES}])])
        drawn, other = named(built, TWO_LINES), named(built, "one")
        self.assertEqual(DEFAULT.line_height(drawn.size), drawn.rect.height - other.rect.height)


class ALineBreakInADate(unittest.TestCase):
    """The name a date that cuts across the page carries."""

    LANES = [lane("One", [bar(0, 6, "work")])]
    CLOSE = [{"at": 2.0, "text": "alphabet soup\nbeta"}, {"at": 2.1, "text": "gamma rays"},
             {"at": 2.2, "text": "delta rays"}, {"at": 2.3, "text": "epsilon"}]

    def test_the_name_takes_a_line_for_each_line_written(self):
        built = page(self.LANES, milestones=[{"at": 3, "text": TWO_LINES}])
        self.assertEqual(2, lines_of(built, TWO_LINES))

    def test_the_page_counts_the_lines_of_a_name_for_the_height_it_needs(self):
        built = page(self.LANES, milestones=self.CLOSE)
        self.assertEqual(0, reaches_below(built))

    def test_the_name_stands_clear_of_the_lanes(self):
        built = page(self.LANES, milestones=[{"at": 3, "text": TWO_LINES}])
        label = named(built, TWO_LINES)
        for drawn in kinds(built, "bar"):
            self.assertLessEqual(label.rect.bottom, drawn.rect.top)

    def test_a_row_stands_as_tall_as_the_tallest_name_in_it(self):
        """近い日付は段を分ける。上の段の名前が 2 行なら、次の段はその高さのぶん下から始まる。"""
        built = page(self.LANES, milestones=self.CLOSE)
        tops = sorted({e.rect.top for e in kinds(built, "label") if e.text.split()[0] in
                       {"alphabet", "gamma", "delta", "epsilon"}})
        self.assertEqual(3, len(tops), "the names stand in fewer rows than they need")
        line = DEFAULT.line_height(named(built, "epsilon").size)
        self.assertEqual(2 * line, tops[1] - tops[0])
        self.assertEqual(line, tops[2] - tops[1])

    def test_the_line_of_a_date_starts_at_the_top_of_its_name(self):
        built = page(self.LANES, milestones=self.CLOSE)
        lines = kinds(built, "line")
        names = [e for e in kinds(built, "label") if e.text.split()[0] in {"alphabet", "gamma", "delta", "epsilon"}]
        self.assertEqual(4, len(lines))
        self.assertEqual(sorted(e.rect.top for e in names), sorted(e.rect.top for e in lines))

    def test_no_name_stands_on_another(self):
        labels = [e for e in kinds(page(self.LANES, milestones=self.CLOSE), "label")]
        for index, first in enumerate(labels):
            for second in labels[index + 1:]:
                self.assertFalse(first.rect.overlaps(second.rect), f"{first.text!r} stands on {second.text!r}")


class ALineBreakInAPeriod(unittest.TestCase):
    """The name of a period, over its column."""

    def test_the_name_takes_a_line_for_each_line_written(self):
        built = page([lane("One", [bar(0, 6, "work")])], periods=["Jan\nand more", "Feb", "Mar", "Apr", "May", "Jun"])
        period = named(built, "Jan\nand more")
        self.assertGreaterEqual(period.rect.height,
                                2 * DEFAULT.line_height(period.size) + 2 * DEFAULT.spacing.bar_pad_y)

    def test_the_page_counts_the_lines_of_a_name_for_the_height_it_needs(self):
        built = page([lane("One", [bar(0, 6, "work")])], periods=["Jan\nand more", "Feb", "Mar", "Apr", "May", "Jun"])
        self.assertEqual(0, reaches_below(built))

    def test_every_period_stands_as_tall_as_the_tallest_and_clear_of_the_lanes(self):
        built = page([lane("One", [bar(0, 6, "work")])], periods=["Jan\nand more", "Feb", "Mar", "Apr", "May", "Jun"])
        heights = {e.rect.height for e in kinds(built, "period")}
        self.assertEqual(1, len(heights))
        for period in kinds(built, "period"):
            for drawn in kinds(built, "bar"):
                self.assertLessEqual(period.rect.bottom, drawn.rect.top)


class ALineBreakInASpeechBubble(unittest.TestCase):
    """The words of a voice."""

    SAID = "一行目\n二行目"

    def built(self):
        return compose([row(voices({"text": self.SAID, "who": "作品 A"}))])

    def test_each_line_is_a_paragraph_with_the_alignment_of_the_first(self):
        shape = shape_of(baked(self.built()), "一行目")
        paragraphs = re.findall(r"<a:p>.*?</a:p>", shape, re.S)
        self.assertEqual(2, len(paragraphs))
        self.assertEqual(1, len({re.search(r'<a:pPr algn="(\w+)"', p).group(1) for p in paragraphs}))
        for paragraph, words in zip(paragraphs, self.SAID.split("\n")):
            self.assertIn(f">{words}<", paragraph)
        self.assertNotIn("\n", "".join(re.findall(r"<a:t>(.*?)</a:t>", shape, re.S)))

    def test_the_bubble_is_as_tall_as_its_lines(self):
        one = compose([row(voices({"text": "一行目", "who": "作品 A"}))])
        self.assertEqual(DEFAULT.line_height(DEFAULT.type.body),
                         kinds(self.built(), "voice")[0].rect.height - kinds(one, "voice")[0].rect.height)


#: 改行を足してよい名前のキー (= どの型でも、書かれた名前を持つ)
TEXT_KEYS = {"text", "heading", "body", "name", "label", "note", "caption", "settled", "lead", "tag", "lane",
             "period", "phases", "milestones", "periods", "marks", "bars"}
SECOND = "にぎょうめ"


def broken(found, key=None):
    """A page's declaration with a second line added to every name it writes."""
    if isinstance(found, dict):
        return {k: broken(v, k) for k, v in found.items()}
    if isinstance(found, list):
        return [broken(v, key) for v in found]
    if isinstance(found, str) and key in TEXT_KEYS and found.strip() and "\n" not in found:
        return found + "\n" + SECOND
    return found


class ABreakInEveryNameOfTheCorpus(unittest.TestCase):
    """Every page of the corpus, built with a second line in each of its names.

    ⚠ **拒む頁は書かれたままで組む** (= 「1 行で書く」札などは、改行を拒むのが決まり。拒みは文で言う)。
    """

    def test_no_box_is_shorter_than_its_lines_and_no_run_holds_a_break(self):
        real, found = types.build, []

        def with_breaks(spec, asset, aspect, theme):
            try:
                built = real(broken(copy.deepcopy(spec)), asset, aspect, theme)
                elements = built.build()
            except (PageTypeError, PageFullError):
                return real(spec, asset, aspect, theme)
            for element in elements:
                if isinstance(element, (Text, Bar)) and "\n" in element.text:
                    need = (element.text.count("\n") + 1) * theme.line_height(element.size)
                    if element.rect.height < need - 2:
                        found.append(f"{spec.get('type')}: {element.text!r} is {element.rect.height} tall, needs {need}")
            return real(broken(copy.deepcopy(spec)), asset, aspect, theme)

        types.build = with_breaks
        try:
            with tempfile.TemporaryDirectory() as out:
                baked_pages = snapshot.bake(REPO / "tests" / "corpus", Path(out))
                for path in baked_pages:
                    if path.name.startswith("page-") and path.suffix == ".xml":
                        for words in re.findall(r"<a:t>([^<]*\n[^<]*)</a:t>", path.read_text(encoding="utf-8")):
                            found.append(f"{path.parent.name}/{path.name}: a break inside one run: {words!r}")
        finally:
            types.build = real
        self.assertEqual([], sorted(set(found)))


if __name__ == "__main__":
    unittest.main()
