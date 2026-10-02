"""The timeline: periods left to right, lanes top to bottom, bars and marks on the lanes.

⚠ **この型は、絵で描いて貼った計画の頁を人が直せなかったために在る。**だから見張るのは
3 つ ― 文字が全部 pptx の文字として残ること、位置が期間の番号だけで決まること、
収まらないものを縮めずに止めること。
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker import checks  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.page import Bar, Diamond, PageFullError, Text  # noqa: E402
from pptx_agent_maker.layout.tokens import DEFAULT  # noqa: E402
from pptx_agent_maker.layout.types import PageTypeError  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]


def page(lanes, *, periods=MONTHS, **extra):
    return types.build({"type": "timeline", "title": "A plan", "periods": periods,
                        "lanes": lanes, **extra}, lambda name: Path(name), lambda path: 1.0)


def lane(name="Work", bars=(), marks=()):
    return {"name": name, "bars": list(bars), "marks": list(marks)}


def bar(start, end, text="step", **more):
    return {"from": start, "to": end, "text": text, **more}


def of(built, kind):
    return [element for element in built.build() if element.kind == kind]


def named(built, text):
    return next(e for e in built.build() if getattr(e, "text", None) == text)


def columns(built):
    """The left edge of each period's column, read off the period names."""
    return [named(built, month).rect.left for month in MONTHS]


class WhereThingsLand(unittest.TestCase):
    """A position is a period number; the type turns it into a place."""

    def test_a_bar_runs_from_the_start_of_its_first_period_to_the_end_of_its_last(self):
        built = page([lane(bars=[bar(1, 3, "build")])])
        edges, gap = columns(built), DEFAULT.spacing.bar_gap
        drawn = named(built, "build").rect
        self.assertEqual(drawn.left, edges[1] + gap)
        self.assertEqual(drawn.right, edges[3] - gap)

    def test_half_a_period_is_half_a_column(self):
        built = page([lane(bars=[bar(0, 0.5, "a"), bar(0.5, 1, "b")])])
        first, second = named(built, "a").rect, named(built, "b").rect
        self.assertAlmostEqual(first.width, second.width, delta=2)
        self.assertLess(first.right, second.left)

    def test_bars_that_only_touch_share_a_row_and_bars_that_overlap_do_not(self):
        built = page([lane(bars=[bar(0, 2, "first"), bar(2, 4, "second"), bar(3, 5, "third")])])
        first, second, third = (named(built, t).rect for t in ("first", "second", "third"))
        self.assertEqual(first.top, second.top)
        self.assertGreaterEqual(third.top, second.bottom)
        self.assertFalse(second.overlaps(third))

    def test_lanes_stack_top_to_bottom_in_the_order_written(self):
        built = page([lane("One", [bar(0, 6, "a")]), lane("Two", [bar(0, 6, "b")])])
        self.assertLess(named(built, "a").rect.bottom, named(built, "b").rect.top)
        self.assertLess(named(built, "One").rect.top, named(built, "Two").rect.top)

    def test_a_mark_is_a_diamond_centred_on_its_moment_with_its_name_beside_it(self):
        built = page([lane(bars=[bar(4, 6, "later")], marks=[{"at": 2, "text": "release"}])])
        diamond = [e for e in built.build() if isinstance(e, Diamond)][0].rect
        self.assertEqual(diamond.width, diamond.height)
        self.assertAlmostEqual(diamond.left + diamond.width // 2, columns(built)[2], delta=1)
        self.assertGreater(named(built, "release").rect.left, diamond.right)

    def test_marks_at_both_ends_of_the_axis_stay_on_the_page(self):
        built = page([lane(marks=[{"at": 0, "text": "start"}, {"at": 6, "text": "end"}])])
        frame = built.theme.frame()
        for element in built.build():
            self.assertTrue(frame.contains(element.rect), f"{element.kind} left the frame")
        # 右端では名前を置く場所が左にしか無い
        diamonds = sorted((e.rect for e in built.build() if isinstance(e, Diamond)),
                          key=lambda r: r.left)
        self.assertLess(named(built, "end").rect.right, diamonds[-1].left)
        self.assertEqual("right", named(built, "end").align)

    def test_everything_on_a_crowded_page_stays_inside_the_frame(self):
        lanes = [lane(f"Lane {n}", [bar(0, 2, "one"), bar(1, 4, "two"), bar(3.5, 6, "three")],
                      [{"at": n, "text": "check"}]) for n in range(1, 4)]
        built = page(lanes, phases=[{"from": 0, "to": 3, "label": "early"},
                                    {"from": 3, "to": 6, "label": "late"}],
                     milestones=[{"at": 2.5, "text": "review"}, {"at": 6, "text": "close"}])
        frame = built.theme.frame()
        for element in built.build():
            self.assertTrue(frame.contains(element.rect), f"{element.kind} left the frame")


class TheWordsStayWords(unittest.TestCase):
    """Every name is text a person can edit, and a bar carries its own."""

    def test_a_bar_holds_its_name_in_the_same_shape(self):
        drawn = named(page([lane(bars=[bar(0, 3, "build the core")])]), "build the core")
        self.assertIsInstance(drawn, Bar)

    def test_no_name_is_set_below_the_floor(self):
        built = page([lane("A lane", [bar(0, 1, "x"), bar(2, 2.2, "a long name for a short bar")],
                           [{"at": 5, "text": "mark"}])], milestones=[{"at": 3, "text": "date"}])
        sizes = {e.size for e in built.build() if isinstance(e, (Bar, Text))}
        self.assertGreaterEqual(min(sizes), DEFAULT.type.minimum)

    def test_a_name_too_long_for_one_line_takes_two_inside_the_bar(self):
        short = named(page([lane(bars=[bar(0, 1, "short")])]), "short").rect
        text = "hand over the face input to the team"
        long = named(page([lane(bars=[bar(0, 1, text)])]), text)
        self.assertIsInstance(long, Bar)
        self.assertGreater(long.rect.height, short.height)
        fits = "hand over the input"
        self.assertEqual(short.height, named(page([lane(bars=[bar(0, 1, fits)])]), fits).rect.height)

    def test_a_single_word_is_never_folded_in_the_middle(self):
        """1 語の名前を 2 行に折ると、語の途中で切れる (= 焼いて初めて出た)。"""
        built = page([lane(bars=[bar(2, 2.3, "auditing")])], periods=MONTHS)
        self.assertIsInstance(named(built, "auditing"), Text)
        self.assertEqual(1, len([e for e in built.build() if isinstance(e, Bar) and not e.text]))

    def test_a_name_too_long_for_two_lines_goes_beside_the_bar_uncut(self):
        text = "a name far too long for a bar this short"
        built = page([lane(bars=[bar(1, 1.5, text)])])
        label = named(built, text)
        self.assertIsInstance(label, Text)
        empty = [e for e in built.build() if isinstance(e, Bar) and not e.text]
        self.assertEqual(1, len(empty))
        self.assertGreaterEqual(label.rect.left, empty[0].rect.right)
        self.assertEqual(label.rect.top, empty[0].rect.top)

    def test_a_name_beside_a_bar_keeps_the_next_bar_off_it(self):
        text = "a name far too long for a bar this short"
        built = page([lane(bars=[bar(1, 1.5, text), bar(2, 4, "next")])])
        self.assertGreaterEqual(named(built, "next").rect.top, named(built, text).rect.bottom)

    def test_a_tentative_bar_is_a_dashed_outline_on_paper(self):
        built = page([lane(bars=[bar(0, 2, "sure"), bar(2, 4, "maybe", tentative=True)])])
        sure, maybe = named(built, "sure"), named(built, "maybe")
        self.assertTrue(maybe.dashed and maybe.outline)
        self.assertEqual(DEFAULT.palette.paper, maybe.fill)
        self.assertFalse(sure.dashed or sure.outline)
        self.assertNotEqual(DEFAULT.palette.paper, sure.fill)

    def test_neighbouring_lanes_differ_in_tone_and_use_only_palette_colours(self):
        built = page([lane("One", [bar(0, 6, "a")]), lane("Two", [bar(0, 6, "b")])])
        self.assertNotEqual(named(built, "a").fill, named(built, "b").fill)
        palette = set(vars(DEFAULT.palette).values())
        for element in built.build():
            for colour in (getattr(element, "colour", ""), getattr(element, "fill", ""),
                           getattr(element, "outline", "")):
                if colour:
                    self.assertIn(colour, palette, f"{element.kind} uses a colour of its own")


class DatesThatCutAcross(unittest.TestCase):
    """A milestone is a line through every lane, with its name flying from the top of it."""

    LANES = [lane("One", [bar(0, 6, "a")]), lane("Two", [bar(0, 6, "b")])]

    def test_the_line_runs_from_its_name_to_the_bottom_of_the_last_lane(self):
        built = page(self.LANES, milestones=[{"at": 3, "text": "review"}])
        line, name = of(built, "line")[0].rect, named(built, "review").rect
        self.assertEqual(line.top, name.top)
        self.assertGreater(line.bottom, named(built, "b").rect.bottom)
        self.assertAlmostEqual(line.left + line.width // 2, columns(built)[3], delta=1)
        self.assertEqual(name.left - line.right, DEFAULT.spacing.bar_pad_x - DEFAULT.spacing.hairline)

    def test_the_line_is_laid_under_the_bars(self):
        """上に引くと、棒の名前を貫く (= 焼いて初めて出た)。"""
        kinds = [e.kind for e in page(self.LANES, milestones=[{"at": 3, "text": "x"}]).build()]
        self.assertLess(kinds.index("line"), kinds.index("bar"))

    #: 名前が線に貫かれうる並び ― 近い日付が続く / 右端で名前が左へ出て手前の線に掛かる /
    #: 長い名前の下を、後から来た線がくぐる
    CROWDED = {
        "close together": [{"at": 3, "text": "a long review name"}, {"at": 3.3, "text": "budget lock"},
                           {"at": 3.6, "text": "another one close by"}, {"at": 5.9, "text": "launch"}],
        "a name flying left at the edge": [{"at": 5, "text": "early"},
                                           {"at": 5.95, "text": "a long name near the edge"}],
        "a late line under a long name": [
            {"at": 1, "text": "a long name that runs on and on a while"},
            {"at": 2, "text": "another long name that runs far across the page"},
            {"at": 3.5, "text": "short"}],
    }

    def test_no_line_cuts_through_another_milestones_name(self):
        for case, stones in self.CROWDED.items():
            with self.subTest(case):
                built = page(self.LANES, milestones=stones)
                names = [named(built, stone["text"]).rect for stone in stones]
                for line in of(built, "line"):
                    for name in names:
                        self.assertFalse(line.rect.overlaps(name), "a line runs through a name")
                for index, one in enumerate(names):
                    for other in names[index + 1:]:
                        self.assertFalse(one.overlaps(other), "two names share a place")

    def test_the_crowded_cases_are_the_cases_they_say_they_are(self):
        """見本の名前が短くなると、規則の枝を通らないまま緑になる (= 幅の数え方を変えた時に起きた)。"""
        def row(built, text):
            tops = sorted({e.rect.top for e in built.build() if e.kind == "label" and e.bold})
            return tops.index(named(built, text).rect.top)

        built = page(self.LANES, milestones=self.CROWDED["close together"])
        self.assertEqual([0, 1, 2], [row(built, s["text"]) for s in self.CROWDED["close together"][:3]])
        built = page(self.LANES, milestones=self.CROWDED["a name flying left at the edge"])
        self.assertEqual((1, 0), (row(built, "early"), row(built, "a long name near the edge")))
        built = page(self.LANES, milestones=self.CROWDED["a late line under a long name"])
        self.assertEqual(2, row(built, "short"), "the short name had room on the first row but for the line")

    def test_a_name_with_no_room_on_the_right_flies_left_from_its_line(self):
        built = page(self.LANES, milestones=self.CROWDED["a name flying left at the edge"])
        name = named(built, "a long name near the edge")
        line = max(of(built, "line"), key=lambda e: e.rect.left).rect
        self.assertEqual("right", name.align)
        self.assertLess(name.rect.right, line.left)
        self.assertEqual(name.rect.top, line.top)

    def test_a_name_beside_a_bar_moves_to_the_side_no_line_crosses(self):
        text = "a name far too long for a bar this short"
        free = page([lane(bars=[bar(3, 3.2, text)])])
        crossed = page([lane(bars=[bar(3, 3.2, text)])], milestones=[{"at": 4, "text": "x"}])
        self.assertEqual("left", named(free, text).align)
        self.assertEqual("right", named(crossed, text).align)

    def test_a_tentative_bar_hides_the_line_behind_it(self):
        built = page([lane(bars=[bar(2, 4, "maybe", tentative=True)])],
                     milestones=[{"at": 3, "text": "x"}])
        self.assertTrue(named(built, "maybe").fill, "an unfilled bar lets the line through its name")


class WhatItRefuses(unittest.TestCase):
    """A declaration nobody can draw stops here, and says what to change."""

    def refused(self, lanes, message, **extra):
        with self.assertRaises(PageTypeError) as raised:
            page(lanes, **extra)
        self.assertIn(message, str(raised.exception))

    def test_a_position_outside_the_periods(self):
        self.refused([lane(bars=[bar(0, 7)])], "outside the 6 periods")
        self.refused([lane(marks=[{"at": -1, "text": "x"}])], "outside the 6 periods")

    def test_a_position_that_is_not_a_number(self):
        self.refused([lane(bars=[bar("Jan", 2)])], "period number")
        self.refused([lane(bars=[bar(True, 2)])], "period number")
        self.refused([lane(bars=[{"to": 2, "text": "x"}])], "period number")

    def test_a_bar_that_ends_before_it_starts(self):
        self.refused([lane(bars=[bar(3, 3)])], "end after it starts")
        self.refused([lane(bars=[bar(4, 2)])], "end after it starts")

    def test_a_key_nobody_reads_at_every_level(self):
        self.refused([{"name": "x", "bars": [bar(0, 1)], "colour": "red"}], "does not take colour")
        self.refused([lane(bars=[bar(0, 1, left=3)])], "does not take left")
        self.refused([lane(marks=[{"at": 1, "text": "x", "x": 3}])], "does not take x")
        self.refused([lane(bars=[bar(0, 1)])], "does not take width",
                     phases=[{"from": 0, "to": 1, "label": "p", "width": 3}])
        self.refused([lane(bars=[bar(0, 1)])], "does not take top",
                     milestones=[{"at": 1, "text": "m", "top": 3}])

    def test_milestones_written_under_a_lane_say_where_they_belong(self):
        """TOML では `[[pages.lanes]]` の下に書いたキーはそのレーンの物になる。"""
        self.refused([{"name": "x", "bars": [bar(0, 1)], "milestones": [{"at": 1, "text": "m"}]}],
                     "above the first `[[pages.lanes]]`")

    def test_no_periods_no_lanes_or_a_lane_with_nothing_on_it(self):
        self.refused([lane(bars=[bar(0, 1)])], "`periods` is empty", periods=[])
        self.refused([], "`lanes` is empty")
        self.refused([lane()], "neither bars nor marks")

    def test_phases_that_overlap(self):
        self.refused([lane(bars=[bar(0, 1)])], "starts before the one before it ends",
                     phases=[{"from": 0, "to": 3, "label": "a"}, {"from": 2, "to": 5, "label": "b"}])


class WhatDoesNotFitIsNotShrunk(unittest.TestCase):

    def test_more_lanes_than_the_page_holds(self):
        with self.assertRaises(PageFullError) as raised:
            page([lane(f"Lane {n}", [bar(0, 6, "work")]) for n in range(30)])
        self.assertIn("will not shrink", str(raised.exception))

    def test_a_period_name_wider_than_its_column(self):
        with self.assertRaises(PageFullError):
            page([lane(bars=[bar(0, 1)])], periods=["a period with a very long name"] * 12)

    def test_a_few_bars_do_not_swell_to_fill_the_page(self):
        """余った高さを配り切ると、棒 1 本の線表が頁いっぱいの帯になる。"""
        built = page([lane(bars=[bar(0, 6, "only")])])
        natural = DEFAULT.line_height(DEFAULT.type.caption) + 2 * DEFAULT.spacing.bar_pad_y
        self.assertLessEqual(named(built, "only").rect.height, round(natural * (1 + types.ROOMY)))
        self.assertGreater(named(built, "only").rect.height, natural)

    def test_a_full_page_keeps_its_bars_at_their_natural_height(self):
        lanes = [lane(f"Lane {n}", [bar(0, 6, "work")]) for n in range(10)]
        natural = DEFAULT.line_height(DEFAULT.type.caption) + 2 * DEFAULT.spacing.bar_pad_y
        heights = {e.rect.height for e in page(lanes).build() if isinstance(e, Bar)}
        self.assertLess(max(heights), round(natural * (1 + types.ROOMY)))


class OnceBaked(unittest.TestCase):
    """What the writer puts in the file: shapes PowerPoint has no reason to repair."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        built = page([lane("Core", [bar(0, 2, "build"), bar(2, 2.3, "a name that goes beside it"),
                                    bar(3, 5, "maybe", tentative=True)],
                           [{"at": 2, "text": "release"}])],
                     phases=[{"from": 0, "to": 6, "label": "this half"}],
                     milestones=[{"at": 5.5, "text": "review"}])
        deck = new_deck()
        add_page(deck, built.build())
        cls.deck = save(deck, Path(cls.tmp.name) / "timeline.pptx")
        with zipfile.ZipFile(cls.deck) as archive:
            cls.xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        cls.shapes = re.findall(r"<p:sp>.*?</p:sp>", cls.xml, re.S)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def shape(self, text):
        return next(s for s in self.shapes if f">{text}<" in s)

    def test_the_only_preset_shape_is_the_rectangle(self):
        self.assertEqual({"rect"}, set(re.findall(r'<a:prstGeom prst="(\w+)"', self.xml)))

    def test_the_diamond_is_a_square_turned_45_degrees(self):
        turned = [s for s in self.shapes if 'rot="2700000"' in s]
        self.assertEqual(1, len(turned))
        width, height = re.search(r'<a:ext cx="(\d+)" cy="(\d+)"', turned[0]).groups()
        self.assertEqual(width, height)

    def test_a_tentative_bar_has_a_dashed_line_and_a_normal_bar_has_none(self):
        self.assertIn('<a:prstDash val="dash"/>', self.shape("maybe"))
        self.assertNotIn("prstDash", self.shape("build"))
        self.assertRegex(self.shape("build"), r"<a:ln[^>]*>\s*<a:noFill/>")

    def test_no_shape_borrows_the_themes_shape_style(self):
        """参照が残ると、LibreOffice で焼いた絵にだけ影が付く。"""
        self.assertNotIn("<p:style>", self.xml)

    def test_a_bar_and_its_name_are_one_shape(self):
        self.assertIn("<a:solidFill>", self.shape("build").split("<p:txBody>")[0])

    def test_a_name_beside_something_is_not_wrapped(self):
        for text in ("release", "review", "a name that goes beside it", "Jan"):
            self.assertIn('wrap="none"', self.shape(text), text)
        self.assertIn('wrap="square"', self.shape("build"))

    def test_no_run_is_empty(self):
        self.assertNotRegex(self.xml, r"<a:t\s*/>|<a:t></a:t>")

    def test_the_checks_find_nothing(self):
        self.assertEqual([], checks.run_all(self.deck))

    def test_python_pptx_opens_it_again(self):
        from pptx import Presentation
        self.assertEqual(1, len(Presentation(str(self.deck)).slides))


class TheWidthOfOneLine(unittest.TestCase):
    """Whether a name fits on one line is measured, not assumed."""

    def test_a_full_width_character_is_one_em_and_a_narrow_one_less(self):
        em = DEFAULT.width("全", 10)
        self.assertEqual(em * 3, DEFAULT.width("全角字", 10))
        self.assertLess(DEFAULT.width("abc", 10), em * 3)
        self.assertGreater(DEFAULT.width("abc", 10), em * 3 // 2,
                           "narrower than what the overlap check assumes leaves no slack")

    def test_bold_runs_wider(self):
        self.assertGreater(DEFAULT.width("name", 10, bold=True), DEFAULT.width("name", 10))

    def test_only_the_longest_line_counts(self):
        self.assertEqual(DEFAULT.width("abcdef", 10), DEFAULT.width("ab\nabcdef\nabc", 10))


if __name__ == "__main__":
    unittest.main()
