"""A card with no `tone`, in a project that names its own grounds (= `untoned_cards`).

⚠ **地に名前 (= 意味) を付けた案件で `tone` を書き忘れたカードは、道具の既定の薄い地になる。**案件の橙の地と
既定の薄い橙が見分けられず、「急に色が変わった、橙の箱だらけ」と見えた。名前を宣言していない案件は見ない。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.checks import DECLARED  # noqa: E402
from pptx_agent_maker.checks.declared import untoned_cards  # noqa: E402
from pptx_agent_maker.layout.tokens import DEFAULT, theme_from  # noqa: E402

NAMED = theme_from({"grounds": {"Single": "FCE4CC", "Shared": "EEEEEE"}})


def declared(**data) -> SimpleNamespace:
    return SimpleNamespace(kind="declare", data={"type": "cards", "title": "A page", **data})


def said(*entries, theme=NAMED, config=None) -> list[tuple[int, str]]:
    return [(found.page, found.why) for found in untoned_cards.run(SimpleNamespace(entries=list(entries)), theme,
                                                                    config or {})]


class ACardWithNoTone(unittest.TestCase):
    def test_it_runs_with_the_other_checks_of_the_manifest(self) -> None:
        self.assertIn(untoned_cards, DECLARED)

    def test_cards_without_a_tone_are_counted_on_their_page(self) -> None:
        found = said(declared(cards=[{"heading": "A", "tone": "Single"}, {"heading": "B"}, ["C", "c"]]))
        self.assertEqual([1], [page for page, _why in found])
        self.assertIn("2 cards with no `tone`", found[0][1])
        self.assertIn("box", found[0][1])

    def test_every_card_with_a_tone_says_nothing(self) -> None:
        self.assertEqual([], said(declared(cards=[{"heading": "A", "tone": "Single"}, {"heading": "B", "tone": "box"}])))

    def test_a_card_in_a_cell_and_in_a_cell_inside_a_cell_is_read(self) -> None:
        page = declared(type="compose", rows=[{"cells": [{"card": {"heading": "A"}},
                                                         {"rows": [{"cells": [{"card": ["B", "b"]}]}]}]}])
        self.assertIn("2 cards", said(page)[0][1])

    def test_a_project_that_names_no_ground_is_not_read(self) -> None:
        self.assertEqual([], said(declared(cards=[["A", "a"]]), theme=DEFAULT))

    def test_copied_pages_are_not_read(self) -> None:
        self.assertEqual([(2, )], [(page, ) for page, _ in said(SimpleNamespace(kind="copy", data={"cards": [["A", "a"]]}),
                                                                declared(cards=[{"heading": "A"}]))])

    def test_a_project_may_switch_it_off(self) -> None:
        self.assertEqual([], said(declared(cards=[["A", "a"]]), config={"untoned_cards": False}))


if __name__ == "__main__":
    unittest.main()
