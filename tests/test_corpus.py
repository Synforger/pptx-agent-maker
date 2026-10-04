"""The corpus has to use everything a page can be written with.

snapshot (= `scripts/check/snapshot.py`) が「変わっていない」と言えるのは、見本が踏んだ所だけ。
型やキーを足して見本に足し忘れると、そこは作り直しで動いても誰も気づかない。ここでは道具の側の
一覧 (= 型の登録、部品、見た目のキー、色の役) を見本と突き合わせる ― 足した物が見本に無ければ、
足した時点で赤になる。
"""

from __future__ import annotations

import sys
import tomllib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.types.bodies import chart as charts  # noqa: E402
from pptx_agent_maker.layout.types.bodies.compose import BODIES, PARTS  # noqa: E402
from pptx_agent_maker.layout.parts.look import TONES  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import TYPES, EXTRA_KEYS, FRAME_KEYS  # noqa: E402
from pptx_agent_maker.layout.types.core.read import HARVEY, LOOK_KEYS, MARKS  # noqa: E402
from pptx_agent_maker.project.files.manifest import KINDS  # noqa: E402

CORPUS = REPO / "tests" / "corpus"


def _toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


RECIPES = _toml(CORPUS / "recipes.toml")["recipes"]
WRITTEN = [page for manifest in sorted((CORPUS / "manifests").glob("*.toml"))
           for page in _toml(manifest)["pages"]]
#: 宣言として組まれる頁 (= recipe の頁は、recipe が決めたキーを足して読む)
DECLARED = [page if page["kind"] == "declare" else {**RECIPES[page["recipe"]], **page}
            for page in WRITTEN if page["kind"] in ("declare", "recipe")]


def cells(rows: list) -> list[dict]:
    """Every cell of a compose, however deep its rows nest."""
    found = []
    for row in rows:
        for cell in row["cells"]:
            found.append(cell)
            found += cells(cell.get("rows", []))
    return found


CELLS = [cell for page in DECLARED if page["type"] == "compose" for cell in cells(page["rows"])]


def bodies(name: str) -> list[dict]:
    """Every place a type is written: as a page of its own, and laid into a cell."""
    return [page for page in DECLARED if page["type"] == name] + [cell[name] for cell in CELLS if name in cell]


def tables(found) -> list[dict]:
    """Every table of keys under something, itself included."""
    if isinstance(found, dict):
        return [found] + [table for value in found.values() for table in tables(value)]
    if isinstance(found, list):
        return [table for value in found for table in tables(value)]
    return []


class TheCorpusUsesEverything(unittest.TestCase):
    def test_every_way_to_make_a_page(self) -> None:
        self.assertEqual(set(KINDS), {page["kind"] for page in WRITTEN})

    def test_every_type_as_a_page_of_its_own(self) -> None:
        self.assertEqual(set(types.names()), {page["type"] for page in DECLARED})

    def test_every_key_a_type_reads(self) -> None:
        for name, (_filler, needs, takes, _figure) in TYPES.items():
            with self.subTest(name):
                used = {key for body in bodies(name) for key in body}
                self.assertEqual(set(), (needs | takes) - used, f"{name}: keys the corpus never writes")

    def test_every_extra_and_every_key_of_the_frame(self) -> None:
        used = {key for page in DECLARED for key in page}
        self.assertEqual(set(), (EXTRA_KEYS | FRAME_KEYS) - used)

    def test_every_part_and_every_type_a_cell_may_hold(self) -> None:
        used = {key for cell in CELLS for key in cell}
        self.assertEqual(set(), {"rows", "weight", "caption", *PARTS, *BODIES} - used)

    def test_every_look_on_everything_shaped_like_a_box(self) -> None:
        bars = [bar for body in bodies("timeline") for lane in body["lanes"] for bar in lane.get("bars", [])]
        boxes = {
            "a card": [card for page in DECLARED for card in page.get("cards", [])],
            "a card in a cell": [cell["card"] for cell in CELLS if "card" in cell],
            "a node of a flow": [node for body in bodies("flow") for stage in body["stages"]
                                 for node in stage["nodes"]],
            "a node of a roadmap": [node for body in bodies("roadmap") for stage in body["stages"]
                                    for node in stage["nodes"]],
            "a stage of a roadmap": [stage for body in bodies("roadmap") for stage in body["stages"]],
            "a bar": [bar for bar in bars if bar.get("spans", 1) == 1],
            "a bar across lanes": [bar for bar in bars if bar.get("spans", 1) > 1],
        }
        for what, written in boxes.items():
            with self.subTest(what):
                used = {key for box in written if isinstance(box, dict) for key in box}
                self.assertEqual(set(), set(LOOK_KEYS) - used, f"{what}: looks the corpus never writes")

    def test_every_tone_and_every_ground_the_corpus_names(self) -> None:
        named = set(_toml(CORPUS / "workspace.toml")["theme"]["grounds"])
        self.assertTrue(named, "the corpus names no ground of its own")
        used = {table["tone"] for table in tables(DECLARED) if "tone" in table}
        self.assertEqual(set(), (set(TONES) | named) - used)

    def test_every_kind_of_chart_and_every_key_one_reads(self) -> None:
        written = [page["chart"] for page in DECLARED if page["type"] == "chart"] + \
                  [cell["chart"] for cell in CELLS if "chart" in cell]
        self.assertEqual(set(charts.KINDS), {chart["kind"] for chart in written})
        self.assertEqual(set(), set(charts.KEYS) - {key for chart in written for key in chart})
        self.assertEqual(set(), set(charts.SERIES_KEYS) - {key for chart in written
                                                           for series in chart.get("series", []) for key in series})
        self.assertTrue(any("chart" in cell for cell in CELLS), "no chart is laid into a cell")
        pointed = [chart for chart in written if "callouts" in chart]
        self.assertEqual(set(), set(charts.CALLOUT_KEYS) - {key for chart in pointed
                                                            for callout in chart["callouts"] for key in callout})
        # 注記は、言葉を上に置く種類と右に置く種類、柱を丸ごと指す種類で置き方が違う
        self.assertLessEqual({"column", "line", "bar", "waterfall"}, {chart["kind"] for chart in pointed})

    def test_every_mark_a_cell_may_hold(self) -> None:
        written = [cell for table in tables(DECLARED) for key in ("harvey", "mark") if key in table
                   for cell in [(key, table[key])]]
        self.assertEqual({("harvey", level) for level in range(len(HARVEY))} | {("mark", name) for name in MARKS},
                         set(written))
        in_a_cell = [value for cell in CELLS if "table" in cell for row in cell["table"] for value in row
                     if isinstance(value, dict)]
        self.assertTrue(in_a_cell, "no table laid into a cell holds a mark")

    def test_every_picture_it_carries(self) -> None:
        """⚠ 使われない絵は、見本が何を踏んでいるかを読む人を迷わせる (= 消す)。"""
        written = (CORPUS / "recipes.toml").read_text(encoding="utf-8") + "".join(
            manifest.read_text(encoding="utf-8") for manifest in (CORPUS / "manifests").glob("*.toml"))
        for picture in sorted((CORPUS / "assets").iterdir()):
            with self.subTest(picture.name):
                self.assertIn(f'"{picture.name}"', written)


if __name__ == "__main__":
    unittest.main()
