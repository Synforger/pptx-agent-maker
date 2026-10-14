"""compose: the body written as rows of cells, one part in each.

見張るのは 4 つ ― 書いた割り方のとおりに並ぶこと (= 指定を曲げずに組めること)、高さが中身で
決まる段と残りを分け合う段の区別、今の型を 1 マスに丸ごと入れられること、どの段のどのマスが
悪いかを言って止まること。
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import box_of, named  # noqa: E402

from pptx_agent_maker import checks  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Bar, Figure, Table, Text  # noqa: E402
from pptx_agent_maker.layout.parts.page import PageFullError  # noqa: E402
from pptx_agent_maker.layout.base.tokens import DEFAULT  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.layout.types.core.stack import card_height  # noqa: E402
from pptx_agent_maker.layout.parts.page import Card, Page  # noqa: E402
from pptx_agent_maker.write import add_page, aspect, new_deck, save  # noqa: E402

DATA = REPO / "tests" / "data"
SQUARE, WIDE = "dot.png", "wide.png"      # 8 x 8, 16 x 4
GAP = DEFAULT.spacing.gap_m


def compose(rows, **extra):
    return types.build({"type": "compose", "title": "A page", "rows": rows, **extra},
                       lambda name: DATA / name, aspect)


def row(*cells, **more):
    return {"cells": list(cells), **more}


def card(heading, body="", **more):
    return {"card": {"heading": heading, "body": body, **more}}


def body_of(**extra):
    """The area a compose page's rows are laid into."""
    return Page("A page", DEFAULT, **extra).body


GOAL = [row(card("Goal", "one thing to reach")), row(card("Left", "holds it up"), card("Right", "holds it too"))]


class AsWritten(unittest.TestCase):
    """The page is divided the way the rows say, and nothing is bent to fit."""

    def test_one_card_across_the_page_and_two_under_it(self):
        built = compose(GOAL)
        goal, left, right = (box_of(built, h).rect for h in ("Goal", "Left", "Right"))
        area = body_of()
        self.assertEqual((area.left, area.width), (goal.left, goal.width))
        self.assertEqual(area.left, left.left)
        self.assertEqual(area.right, right.right)
        self.assertEqual(right.left - left.right, GAP)
        self.assertEqual(left.width, right.width)
        self.assertEqual(goal.bottom + GAP, left.top)

    def test_a_weight_shares_the_width(self):
        built = compose([row(card("One"), {**card("Two"), "weight": 2})])
        one, two = box_of(built, "One").rect, box_of(built, "Two").rect
        self.assertAlmostEqual(2 * one.width, two.width, delta=2)

    def test_the_cards_of_a_row_stand_as_tall_as_the_tallest(self):
        built = compose([row(card("Short", "a"), card("Tall", "a body long enough to break " * 6))])
        self.assertEqual(box_of(built, "Short").rect.height, box_of(built, "Tall").rect.height)

    def test_a_row_of_cards_is_as_tall_as_its_words_and_no_taller(self):
        """頁の高さを配らない (= 字のうしろに空きを残さない)。"""
        built = compose(GOAL)
        goal = box_of(built, "Goal").rect
        self.assertEqual(card_height(built, [Card("Goal", "one thing to reach")], goal.width, 1), goal.height)
        self.assertLess(box_of(built, "Left").rect.bottom, body_of().bottom - DEFAULT.spacing.gap_l)

    def test_rows_nest_inside_a_cell(self):
        built = compose([row(card("Beside"), {"rows": [row(card("Upper")), row(card("Lower"))]})])
        beside, upper, lower = (box_of(built, h).rect for h in ("Beside", "Upper", "Lower"))
        self.assertEqual(upper.left, lower.left)
        self.assertGreater(upper.left, beside.right)
        self.assertEqual(upper.bottom + GAP, lower.top)
        # 入れ子も言葉ぶんの高さなので、隣のカードはその高さに揃う
        self.assertEqual((upper.top, lower.bottom), (beside.top, beside.bottom))

    def test_it_needs_no_picture(self):
        """カードだけの頁 (= 目標と柱) を拒むと、指定を曲げる組み方が戻る。"""
        self.assertTrue(compose(GOAL).build())

    def test_the_parts_any_page_takes_still_come_around_it(self):
        built = compose(GOAL, cards=[["Above", "a"]], table=[["a", "b"], ["1", "2"]], conclusion="So")
        self.assertLess(box_of(built, "Above").rect.bottom, box_of(built, "Goal").rect.top)
        table = next(e for e in built.build() if isinstance(e, Table) and e.rect.top > box_of(built, "Left").rect.bottom)
        self.assertTrue(table)


class Heights(unittest.TestCase):
    """Rows of words keep their own height; rows of pictures and diagrams share what is left."""

    def test_a_picture_row_takes_what_the_word_rows_leave(self):
        built = compose([row(card("Words")), row({"figure": SQUARE})])
        picture = next(e for e in built.build() if isinstance(e, Figure)).rect
        start = box_of(built, "Words").rect.bottom + GAP
        self.assertLessEqual(picture.bottom, body_of().bottom)
        self.assertAlmostEqual(body_of().bottom - start, picture.height, delta=2)

    def test_two_sharing_rows_split_by_their_weights(self):
        built = compose([row({"figure": WIDE}, weight=1),
                         row({"timeline": {"periods": ["a", "b"],
                                           "lanes": [{"name": "L", "bars": [{"from": 0, "to": 2, "text": "x"}]}]}},
                             weight=3)])
        picture = next(e for e in built.build() if isinstance(e, Figure)).rect
        lane_name = named(built, "L").rect
        share = (body_of().height - GAP) / 4
        self.assertLessEqual(picture.bottom, body_of().top + share + 2)
        self.assertGreater(lane_name.top, body_of().top + share)

    def test_a_weight_on_a_row_of_cards_makes_it_share(self):
        built = compose([row(card("Grows"), weight=1), row(card("Under"))])
        self.assertLess(box_of(built, "Grows").rect.height, body_of().height,
                        "a card in a sharing row keeps its own height")
        self.assertEqual(body_of().top, box_of(built, "Grows").rect.top)
        # 分け合う段が残りを全部取るので、その下の段は頁の下端まで押される
        self.assertAlmostEqual(body_of().bottom, box_of(built, "Under").rect.bottom, delta=2)

    def test_a_card_beside_a_picture_keeps_its_own_height_at_the_top(self):
        built = compose([row(card("Card", "a"), {"figure": SQUARE})])
        box = box_of(built, "Card").rect
        self.assertEqual(body_of().top, box.top)
        self.assertEqual(card_height(built, [Card("Card", "a")], box.width, 1), box.height)

    def test_a_picture_in_a_cell_sits_at_the_top_with_its_name_just_under_it(self):
        built = compose([row({"figure": WIDE, "caption": "what it shows"}, {"text": "beside it"})])
        picture = next(e for e in built.build() if isinstance(e, Figure)).rect
        name = named(built, "what it shows").rect
        self.assertEqual(body_of().top, picture.top)
        self.assertEqual(picture.bottom + DEFAULT.spacing.gap_s, name.top)
        self.assertEqual(DEFAULT.line_height(DEFAULT.type.caption), name.height)

    def test_words_points_and_a_table_take_their_own_height(self):
        built = compose([row({"text": "a line of words"}, {"points": ["one", "two"]},
                             {"table": [["a", "b"], ["1", "2"]]})])
        words, points = named(built, "a line of words"), named(built, "— one\n— two")
        table = next(e for e in built.build() if isinstance(e, Table))
        self.assertEqual((DEFAULT.type.body, DEFAULT.palette.ink), (words.size, words.colour))
        for placed in (words.rect, points.rect, table.rect):
            self.assertEqual(body_of().top, placed.top)
            self.assertLess(placed.height, DEFAULT.line_height() * 4)


class TypesInACell(unittest.TestCase):
    """A whole page type, written the way that type reads it, in one cell."""

    def test_a_timeline_beside_cards(self):
        built = compose([row({"weight": 2, "timeline": {"periods": ["a", "b", "c"], "lanes": [
            {"name": "Lane", "bars": [{"from": 0, "to": 3, "text": "work"}]}]}}, card("Beside"))])
        work = named(built, "work").rect
        self.assertIsInstance(named(built, "work"), Bar)
        self.assertLess(work.right, box_of(built, "Beside").rect.left)

    def test_a_flow_and_a_roadmap_are_taken_too(self):
        for name, body in (("flow", {"stages": [{"name": "A", "nodes": [["n1", ""]]}, {"name": "B", "nodes": [["n2", ""]]}]}),
                           ("roadmap", {"stages": [{"name": "A", "nodes": [["n1", ""]]},
                                                   {"name": "B", "nodes": [["n2", ""]], "goal": True}]})):
            with self.subTest(name):
                built = compose([row({name: body}), row(card("Under"))])
                self.assertLess(box_of(built, "n1").rect.bottom, box_of(built, "Under").rect.top)

    def test_a_types_own_refusal_says_which_cell(self):
        with self.assertRaises(PageTypeError) as raised:
            compose([row(card("A")), row(card("B"), {"timeline": {"periods": ["a"], "lanes": []}})])
        said = str(raised.exception)
        self.assertIn("compose: row 2, cell 2", said)
        self.assertIn("timeline", said)

    def test_a_type_in_a_cell_reads_only_its_own_keys(self):
        with self.assertRaises(PageTypeError) as raised:
            compose([row({"flow": {"stages": [{"name": "A", "nodes": [["n", ""]]}, {"name": "B", "nodes": [["m", ""]]}],
                                   "cards": [["x", "y"]]}})])
        self.assertIn("does not take cards inside a cell", str(raised.exception))

    def test_a_type_missing_what_it_needs(self):
        with self.assertRaises(PageTypeError) as raised:
            compose([row({"timeline": {"periods": ["a"]}})])
        self.assertIn("timeline: missing lanes", str(raised.exception))


class WhatItRefuses(unittest.TestCase):

    def refused(self, rows, *said, error=PageTypeError):
        with self.assertRaises(error) as raised:
            compose(rows)
        for word in said:
            self.assertIn(word, str(raised.exception))

    def test_no_rows(self):
        self.refused([], "`rows` is empty")

    def test_a_row_without_cells(self):
        self.refused([row(card("A")), {"cells": []}], "compose: row 2 has no cells")

    def test_a_cell_holding_nothing(self):
        self.refused([row({"weight": 1})], "compose: row 1, cell 1 holds nothing")

    def test_a_cell_holding_two_things(self):
        self.refused([row({"card": ["A", ""], "text": "and words"})], "holds card, text", "one part per cell")

    def test_a_key_nobody_reads(self):
        self.refused([row({"card": ["A", ""], "colour": "red"})], "row 1, cell 1 does not take colour")
        self.refused([row(card("A"), height=3)], "compose: row 1 does not take height")

    def test_cards_and_compose_are_not_parts(self):
        """カードはマスごとの `card`、入れ子は `rows` で書く。"""
        self.refused([row({"cards": [["A", ""]]})], "does not take cards")
        self.refused([row({"compose": {"rows": []}})], "does not take compose")

    def test_a_caption_belongs_to_a_figure(self):
        self.refused([row({"card": ["A", ""], "caption": "x"})], "`caption` belongs to a figure")

    def test_a_weight_is_a_share_above_zero(self):
        for value in (0, -1, "2", True):
            with self.subTest(value):
                self.refused([row({**card("A"), "weight": value})], "`weight` is a number above 0")

    def test_a_card_written_wrong_names_its_cell(self):
        self.refused([row(card("A"), {"card": {"body": "no heading"}})], "compose: row 1, cell 2, card")

    def test_too_much_stops_the_page_and_nothing_shrinks(self):
        rows = [row(card(f"Card {n}", "a body long enough to break over a line or two " * 3)) for n in range(12)]
        self.refused(rows, "compose", "nothing will shrink", error=PageFullError)

    def test_a_part_taller_than_the_row_it_shares_stops_the_page(self):
        """⚠ **分け合う段に置いた部品を、段の高さに切り詰めて置いていた。**カードの字は箱からはみ出し、
        文章の枠は字より短かった。"""
        long = "words enough to take several lines in a narrow cell " * 6
        parts = {"card": card("Tall", long), "text": {"text": long}, "points": {"points": [long, long]}}
        for name, part in parts.items():
            with self.subTest(name):
                # 1 段目は高さの 9 分の 1 しか取れない (= 絵は縮むが、言葉は縮まない)
                rows = [row({"figure": SQUARE}, part, weight=1), row({"figure": WIDE}, weight=8)]
                self.refused(rows, f"compose: row 1, cell 2: this {name} needs", "nothing will shrink",
                             error=PageFullError)
                self.assertTrue(compose([row({"figure": SQUARE}, part, weight=1),
                                         row({"figure": WIDE}, weight=1)]).build())

    def test_an_agenda_too_tall_for_its_cell_says_which_cell(self):
        # 一覧 (= 2 行) は収まり、章の箱 2 つが段の高さに収まらない
        rows = [row({"figure": SQUARE}, {"agenda": {"buckets": [["One", []], ["Two", []]]}}, weight=1),
                row({"figure": WIDE}, weight=6)]
        self.refused(rows, "compose: row 1, cell 2: agenda: chapter 1 needs", error=PageFullError)
        listed = [row({"figure": SQUARE}, {"agenda": {"buckets": [["One", ["a", "b", "c"]]]}}, weight=1),
                  row({"figure": WIDE}, weight=6)]
        self.refused(listed, "compose: row 1, cell 2: agenda: the list of items needs", error=PageFullError)

    def test_a_nested_cell_names_its_whole_path(self):
        self.refused([row({"rows": [row(card("A")), row({"weight": 1})]})],
                     "compose: row 1, cell 1: row 2, cell 1 holds nothing")


class OnceBaked(unittest.TestCase):

    def test_a_mixed_page_stays_inside_the_frame_and_the_checks_find_nothing(self):
        built = compose([
            row({"weight": 2, "timeline": {"periods": ["a", "b"], "lanes": [
                {"name": "L", "bars": [{"from": 0, "to": 2, "text": "work"}]}]}},
                {"rows": [row(card("Upper", "a", icon=SQUARE)), row({"points": ["one", "two"]})]}, weight=2),
            row({"figure": WIDE, "caption": "shown"}, {"table": [["a", "b"], ["1", "2"]]}, {"text": "words"}),
        ], conclusion="So")
        frame = built.theme.frame()
        for element in built.build():
            self.assertTrue(frame.contains(element.rect), element.kind)
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck()
            add_page(deck, built.build())
            self.assertEqual([], checks.run_all(save(deck, Path(tmp) / "compose.pptx")))


if __name__ == "__main__":
    unittest.main()


def kinds(page, kind):
    """Every element of that kind, in the order they were placed."""
    return [e for e in page.build() if e.kind == kind]


def voices(*said):
    return {"voices": [dict(item) for item in said]}


class Voices(unittest.TestCase):
    """人の声 (= `voices`): 1 つずつ吹き出しの図形に入り、誰の声かが尾の下に小さく出る。見出しは持たない。
    カードで置いていた間は、短い声にも見出しの行が付いて箱が高くなり、数の札と見分けが付かなかった。"""

    SIX = [{"text": f"「声の {n}」", "who": f"作品 {n}"} for n in "ABCDEF"]

    def test_each_voice_is_one_speech_bubble_with_who_said_it_under_it(self):
        page = compose([row(voices({"text": "「分かりやすかった」", "who": "作品 A"}))])
        bubble, = kinds(page, "voice")
        who, = kinds(page, "voice_who")
        self.assertIsInstance(bubble, Bar)
        self.assertEqual(("voice", "「分かりやすかった」"), (bubble.shape, bubble.text))
        self.assertEqual(("作品 A", DEFAULT.type.caption, DEFAULT.palette.muted), (who.text, who.size, who.colour))
        self.assertGreater(who.rect.top, bubble.rect.bottom, "who said it stands under the tail")

    def test_a_voice_needs_no_heading_and_stands_lower_than_a_card(self):
        said = compose([row(voices({"text": "「良い」"}))])
        boxed = compose([row(card("見出し", "「良い」"))])
        self.assertLess(kinds(said, "voice")[0].rect.height, box_of(boxed, "見出し").rect.height)

    def test_the_width_of_the_cell_decides_how_many_stand_side_by_side_and_rows_are_even(self):
        page = compose([row(voices(*self.SIX))])
        tops = sorted({bubble.rect.top for bubble in kinds(page, "voice")})
        self.assertEqual(2, len(tops))
        for top in tops:
            self.assertEqual(3, sum(1 for bubble in kinds(page, "voice") if bubble.rect.top == top))
        narrow = compose([row(voices(*self.SIX[:2]), {"text": "beside", "weight": 3})])
        self.assertEqual(1, len({bubble.rect.left for bubble in kinds(narrow, "voice")}), "a narrow cell stacks them")

    def test_the_bubbles_of_a_row_stand_as_tall_as_the_tallest(self):
        long = {"text": "「長い声。" + "とても長い声で、折り返して何行にもなる。" * 3 + "」"}
        page = compose([row(voices({"text": "「短い」"}, long))])
        alone = compose([row(voices({"text": "「短い」"}, {"text": "「短い」"}))])
        heights = {bubble.rect.height for bubble in kinds(page, "voice")}
        self.assertEqual(1, len(heights))
        self.assertGreater(heights.pop(), kinds(alone, "voice")[0].rect.height, "the short one grows to the long one")

    def test_a_voice_takes_the_tone_a_box_takes(self):
        page = compose([row(voices({"text": "「a」"}, {"text": "「b」", "tone": "tint"}))])
        plain, tinted = kinds(page, "voice")
        self.assertNotEqual(plain.fill, tinted.fill)

    def test_a_row_of_voices_is_as_tall_as_its_words(self):
        page = compose([row(voices(*self.SIX)), row({"figure": SQUARE})])
        last = max(who.rect.bottom for who in kinds(page, "voice_who"))
        picture = next(e for e in page.build() if isinstance(e, Figure))
        self.assertEqual(last + GAP, picture.rect.top, "the picture row takes what the voices leave")

    def test_what_is_refused(self):
        for cell, words in ((voices(), "at least one"), ({"voices": "a"}, "at least one"),
                            (voices({"who": "A"}), "no `text`"), (voices({"text": "a", "by": "A"}), "by"),
                            (voices({"text": "a", "tone": "neon"}), "tone"), ({"voices": ["a"]}, "write it as")):
            with self.subTest(cell=cell), self.assertRaises(PageTypeError) as refused:
                compose([row(cell)])
            self.assertIn(words, str(refused.exception))

    def test_voices_that_do_not_fit_stop(self):
        many = [{"text": "「" + "長い声" * 20 + "」", "who": "誰か"} for _ in range(30)]
        with self.assertRaises(PageFullError):
            compose([row(voices(*many))])

    def test_voices_in_a_row_that_shares_the_height_stop_and_say_which_cell(self):
        some = [{"text": "「" + "長い声" * 10 + "」", "who": "誰か"} for _ in range(8)]
        with self.assertRaises(PageFullError) as stopped:
            compose([row(voices(*some), weight=1), row({"figure": SQUARE}, weight=6)])
        self.assertIn("give the row a larger `weight`", str(stopped.exception))

    def test_it_is_written_as_a_rounded_callout_with_its_tail_to_the_lower_left(self):
        page = compose([row(voices({"text": "「分かりやすかった」", "who": "作品 A"}))])
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck(DEFAULT)
            add_page(deck, page.build(), DEFAULT)
            saved = save(deck, Path(tmp) / "voices.pptx")
            import zipfile
            with zipfile.ZipFile(saved) as archive:
                xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        self.assertIn('prst="wedgeRoundRectCallout"', xml)
        adjusted = dict(re.findall(r'<a:gd name="(adj\d)" fmla="val (-?\d+)"/>', xml))
        self.assertLess(int(adjusted["adj1"]), 0, "the tail leans to the left")
        self.assertGreater(int(adjusted["adj2"]), 50000, "the tail reaches below the bubble")
        self.assertIn("「分かりやすかった」", xml)


class Roles(unittest.TestCase):
    """文章の役 (= `role`): 頁の主役の数字を特大で、コードと数式の行を等幅で、折らずに。"""

    CODE = "def area(r):\n    return 3.14 * r * r"

    def test_a_display_text_is_twice_the_title_bold_in_the_accent(self):
        (shown,) = kinds(compose([row({"text": "2.4x", "role": "display"}), row({"text": "faster"})]), "display")
        self.assertEqual(shown.size, DEFAULT.type.title * 2)
        self.assertTrue(shown.bold)
        self.assertEqual(shown.colour, DEFAULT.palette.accent)

    def test_a_display_text_takes_the_height_of_its_own_large_lines(self):
        page = compose([row({"text": "2.4x", "role": "display"})])
        (shown,) = kinds(page, "display")
        self.assertEqual(shown.rect.height, DEFAULT.line_height(DEFAULT.type.display))

    def test_code_is_monospaced_as_written_on_a_light_ground(self):
        page = compose([row({"text": self.CODE, "role": "mono"})])
        (box,) = kinds(page, "code_box")
        (code,) = kinds(page, "code")
        self.assertEqual(code.family, "Consolas")
        self.assertEqual(code.text, self.CODE, "the indent is kept")
        self.assertEqual(box.colour, DEFAULT.palette.band)
        s = DEFAULT.spacing
        self.assertEqual(box.rect.height, 2 * DEFAULT.line_height() + 2 * s.pad)
        self.assertTrue(box.rect.contains(code.rect))

    def test_code_is_measured_by_its_monospaced_lines_not_by_the_project_s_face(self):
        """`m` は案件の書体では等幅の倍近く広い。等幅なら 1 行に入る行が、案件の書体の字幅で数えると折れる。"""
        line = "m" * 100
        self.assertGreater(DEFAULT.wraps(line, body_of().width), 1, "the project's face would break it")
        (box,) = kinds(compose([row({"text": line, "role": "mono"})]), "code_box")
        self.assertEqual(box.rect.height, DEFAULT.line_height() + 2 * DEFAULT.spacing.pad)

    def test_a_line_of_code_too_long_for_its_cell_stops_rather_than_breaking(self):
        long = "x = " + " + ".join(f"value_{n}" for n in range(30))
        with self.assertRaises(PageFullError) as stopped:
            compose([row({"text": long, "role": "mono"}, {"text": "beside"})])
        self.assertIn("row 1, cell 1", str(stopped.exception))
        self.assertIn("not broken", str(stopped.exception))

    def test_a_role_is_only_for_a_text_and_only_one_of_the_two(self):
        with self.assertRaises(PageTypeError) as wrong_part:
            compose([row({**card("A"), "role": "display"})])
        self.assertIn("`role` belongs to a text", str(wrong_part.exception))
        with self.assertRaises(PageTypeError) as unknown:
            compose([row({"text": "A", "role": "huge"})])
        self.assertIn("display, mono", str(unknown.exception))

    def test_written_out_the_code_keeps_its_face_and_lines_and_the_checks_find_nothing(self):
        page = compose([row({"text": "98%", "role": "display"}, {"text": self.CODE, "role": "mono"})])
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck(DEFAULT)
            add_page(deck, page.build(), DEFAULT)
            saved = save(deck, Path(tmp) / "roles.pptx")
            self.assertEqual([], checks.run_all(saved))
            import zipfile
            with zipfile.ZipFile(saved) as archive:
                xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        self.assertIn('typeface="Consolas"', xml)
        self.assertIn("<a:t>    return 3.14 * r * r</a:t>", xml)
        self.assertIn('wrap="none"', xml)
