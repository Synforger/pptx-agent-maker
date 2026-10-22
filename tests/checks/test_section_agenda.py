"""A long chapter of several parts comes back to its agenda at the head of each part.

章の頁 (= 目次を除く) が 6 を超え、中の段が 2 つ以上ある章は、中の段の頭ごとに目次を挟む (= 同じ章を
`highlight` し、その段を `highlight_item` で強調した目次)。章の頭の目次 1 枚だけの長い章では、読み手は今どこか、
章が全体でどうまとまっているかを見失う。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.checks import DECLARED  # noqa: E402
from pptx_agent_maker.checks.declared import section_agenda  # noqa: E402

BUCKETS = [["Method", ["Data", "Model"]], ["Results", ["Quality", "Cost", "Time"]], ["Next", []]]


def agenda(chapter: int | None = None, item: int | None = None) -> SimpleNamespace:
    data = {"type": "agenda", "title": "Agenda", "look": "cards", "buckets": BUCKETS}
    if chapter is not None:
        data["highlight"] = chapter
    if item is not None:
        data["highlight_item"] = item
    return SimpleNamespace(kind="declare", data=data)


def pages(count: int) -> list[SimpleNamespace]:
    return [SimpleNamespace(kind="declare", data={"type": "cards", "title": f"page {n}"}) for n in range(count)]


def said(*entries, config=None) -> list[tuple[int, str]]:
    return [(found.page, found.what) for found in section_agenda.run(SimpleNamespace(entries=list(entries)), None,
                                                                     config or {})]


class ALongChapter(unittest.TestCase):
    def test_one_agenda_over_a_long_chapter_of_parts_is_said_at_that_agenda(self) -> None:
        found = section_agenda.run(SimpleNamespace(entries=[*pages(1), agenda(2), *pages(15)]), None, {})
        self.assertEqual([(2, "Results")], [(f.page, f.what) for f in found])
        self.assertIn("highlight_item = 1, 2, 3 not yet", found[0].why)

    def test_an_agenda_at_the_head_of_each_part_is_enough(self) -> None:
        chapter = [agenda(2, 1), *pages(5), agenda(2, 2), *pages(5), agenda(2, 3), *pages(5)]
        self.assertEqual([], said(*chapter))

    def test_the_parts_still_without_one_are_named(self) -> None:
        found = section_agenda.run(SimpleNamespace(entries=[agenda(2, 1), *pages(5), agenda(2, 2), *pages(5)]), None, {})
        self.assertIn("highlight_item = 3 not yet", found[0].why)

    def test_a_chapter_up_to_the_length_or_of_one_part_is_not_said(self) -> None:
        self.assertEqual([], said(agenda(2), *pages(6)))
        self.assertEqual([], said(agenda(3), *pages(20)), "no parts")
        one = SimpleNamespace(kind="declare", data={"type": "agenda", "highlight": 1, "buckets": [["Only", ["One"]]]})
        self.assertEqual([], said(one, *pages(20)), "one part")

    def test_each_chapter_is_counted_up_to_the_next_agenda_that_names_another(self) -> None:
        self.assertEqual([(1, "Method")], said(agenda(1), *pages(7), agenda(2, 1), *pages(3), agenda(2, 2), *pages(3)))
        self.assertEqual([], said(agenda(1), *pages(4), agenda(), *pages(4), agenda(1), *pages(4)),
                         "an agenda that names no chapter ends one; the chapter is counted again from its own")

    def test_the_agendas_are_not_counted_as_pages_of_the_chapter(self) -> None:
        self.assertEqual([], said(agenda(2, 1), *pages(2), agenda(2, 2), *pages(2), agenda(2, 3), *pages(2)))

    def test_a_project_sets_the_length_or_switches_it_off(self) -> None:
        self.assertEqual([], said(agenda(2), *pages(15), config={"section_agenda": 20}))
        self.assertEqual([(1, "Results")], said(agenda(2), *pages(4), config={"section_agenda": 3}))
        self.assertEqual([], said(agenda(2), *pages(15), config={"section_agenda": False}))
        for wrong in (0, "6", 2.5):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                said(agenda(2), *pages(15), config={"section_agenda": wrong})

    def test_it_runs_with_the_other_checks_of_a_manifest(self) -> None:
        self.assertIn(section_agenda, DECLARED)


if __name__ == "__main__":
    unittest.main()
