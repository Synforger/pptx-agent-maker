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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.types.bodies import chart as charts  # noqa: E402
from pptx_agent_maker.layout.types.bodies.arrange import LINK_KEYS  # noqa: E402
from pptx_agent_maker.layout.types.bodies.compose import BODIES, PARTS, ROLES, TEXT_LOOKS  # noqa: E402
from pptx_agent_maker.layout.parts.look import TONES  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import TYPES, EXTRA_KEYS, FRAME_KEYS  # noqa: E402
from pptx_agent_maker.layout.tokens import DERIVED  # noqa: E402
from pptx_agent_maker.layout.types.core.read import CARD_KEYS, HARVEY, LOOK_KEYS, MARKS, PANEL_KEYS  # noqa: E402
from pptx_agent_maker.project.files.manifest import KINDS  # noqa: E402

CORPUS = REPO / "tests" / "corpus"


def _toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


RECIPES = _toml(CORPUS / "recipes.toml")["recipes"]
#: 資料全体の見た目を変えて焼く資料 (= `decks/<名前>/`。`[theme]` は案件に 1 つなので、自分の `workspace.toml` を持つ)
DECKS = sorted((CORPUS / "decks").glob("*/workspace.toml"))
MANIFESTS = sorted((CORPUS / "manifests").glob("*.toml")) + sorted((CORPUS / "decks").glob("*/manifests/*.toml"))
WRITTEN = [page for manifest in MANIFESTS for page in _toml(manifest)["pages"]]
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
            found += cells(cell.get("panel", {}).get("rows", []))
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

    def test_a_roadmap_of_arrowheads_alone_and_one_with_only_some_stages_bare(self) -> None:
        roads = [body["stages"] for body in bodies("roadmap")]
        self.assertTrue(any(all("nodes" not in stage for stage in road) for road in roads),
                        "no roadmap leaves the nodes out of every stage")
        self.assertTrue(any(0 < sum("nodes" not in stage for stage in road) < len(road) for road in roads),
                        "no roadmap leaves the nodes out of some stages only")

    def test_every_extra_and_every_key_of_the_frame(self) -> None:
        used = {key for page in DECLARED for key in page}
        self.assertEqual(set(), (EXTRA_KEYS | FRAME_KEYS) - used)

    def test_every_part_and_every_type_a_cell_may_hold(self) -> None:
        used = {key for cell in CELLS for key in cell}
        self.assertEqual(set(), {"rows", "weight", "caption", *PARTS, *BODIES} - used)

    def test_every_role_a_text_may_have_and_every_look_it_takes(self) -> None:
        texts = [cell for cell in CELLS if "text" in cell]
        self.assertEqual(set(ROLES), {cell["role"] for cell in texts if "role" in cell})
        self.assertEqual(set(), set(TEXT_LOOKS) - {key for cell in texts for key in cell})
        self.assertTrue(any("role" in cell and "tone" in cell for cell in texts), "no text of a role is coloured")

    def test_every_key_of_a_link_and_arrows_both_ways(self) -> None:
        linked = [link for page in DECLARED if page["type"] == "compose" for link in page.get("links", [])]
        self.assertEqual(set(LINK_KEYS), {key for link in linked for key in link})
        self.assertTrue(any("text" in link and "tone" not in link for link in linked), "no words on a grey arrow")
        self.assertTrue(any("text" in link and "tone" in link for link in linked), "no words on a coloured arrow")

    def test_every_key_of_a_panel_in_both_looks_and_a_panel_in_a_panel(self) -> None:
        """A panel is painted by the look of the deck, so each look of the corpus writes every key a panel reads."""
        decks = {"the main project": CORPUS / "manifests",
                 **{path.parent.name: path.parent / "manifests" for path in DECKS
                    if _toml(path).get("theme", {}).get("card_look") == "outlined"}}
        for name, folder in decks.items():
            with self.subTest(name):
                pages = [page for manifest in sorted(folder.glob("*.toml")) for page in _toml(manifest)["pages"]]
                written = [cell["panel"] for page in pages if page.get("type") == "compose"
                           for cell in cells(page["rows"]) if "panel" in cell]
                self.assertEqual(set(PANEL_KEYS), {key for panel in written for key in panel})
                self.assertTrue(any("panel" in cell for panel in written for row in panel["rows"]
                                    for cell in row["cells"]), f"{name}: no panel holds a panel")
                linked = [page for page in pages if page.get("type") == "compose" and page.get("links")]
                inside = {cell["id"] for page in linked for cell in cells(page["rows"]) if "id" in cell}
                self.assertTrue(inside, f"{name}: no cell has an id a link can use")

    def test_a_panel_holds_each_kind_of_part_the_corpus_can_lay_in_a_cell_of_it(self) -> None:
        held = {key for page in DECLARED if page["type"] == "compose" for cell in cells(page["rows"])
                if "panel" in cell for row in cell["panel"]["rows"] for inner in row["cells"] for key in inner}
        self.assertLessEqual({"text", "points", "table", "chart", "card", "figure", "panel"}, held)

    def test_a_bar_with_an_id_a_name_on_several_lines_and_an_arrow_between_bars_in_every_look(self) -> None:
        """棒が読む `id`・名前の中の改行・棒どうしの `links` は、見た目の違う資料のそれぞれで書かれている。"""
        decks = {"the main project": CORPUS / "manifests",
                 **{path.parent.name: path.parent / "manifests" for path in DECKS
                    if _toml(path).get("theme", {}).get("bar_look") == "outlined"}}
        for name, folder in decks.items():
            with self.subTest(name):
                pages = [page for manifest in sorted(folder.glob("*.toml")) for page in _toml(manifest)["pages"]
                         if page.get("type") == "timeline"]
                bars = [bar for page in pages for lane in page["lanes"] for bar in lane.get("bars", [])]
                self.assertTrue(any("id" in bar for bar in bars), f"{name}: no bar has an id")
                self.assertTrue(any("\n" in bar.get("text", "") for bar in bars), f"{name}: no name breaks a line")
                self.assertTrue(any(page.get("links") for page in pages), f"{name}: no arrow between bars")

    def test_every_look_on_everything_shaped_like_a_box(self) -> None:
        bars = [bar for body in bodies("timeline") for lane in body["lanes"] for bar in lane.get("bars", [])]
        boxes = {
            "a card": [card for page in DECLARED for card in page.get("cards", [])],
            "a card in a cell": [cell["card"] for cell in CELLS if "card" in cell],
            "a node of a flow": [node for body in bodies("flow") for stage in body["stages"]
                                 for node in stage["nodes"]],
            "a node of a roadmap": [node for body in bodies("roadmap") for stage in body["stages"]
                                    for node in stage.get("nodes", [])],
            "a stage of a roadmap": [stage for body in bodies("roadmap") for stage in body["stages"]],
            "a bar": [bar for bar in bars if bar.get("spans", 1) == 1],
            "a bar across lanes": [bar for bar in bars if bar.get("spans", 1) > 1],
        }
        for what, written in boxes.items():
            with self.subTest(what):
                used = {key for box in written if isinstance(box, dict) for key in box}
                self.assertEqual(set(), set(LOOK_KEYS) - used, f"{what}: looks the corpus never writes")

    def test_every_key_of_a_card_and_every_way_to_write_its_body(self) -> None:
        written = ([card for page in DECLARED for card in page.get("cards", []) if isinstance(card, dict)]
                   + [cell["card"] for cell in CELLS if "card" in cell])
        self.assertEqual(set(), set(CARD_KEYS) - {key for card in written for key in card})
        self.assertTrue(any(isinstance(card.get("body"), list) for card in written), "no card has a list of bullets")
        self.assertTrue(any(isinstance(card.get("body"), str) for card in written))
        self.assertTrue(any(not card.get("heading") for card in written), "no card leaves its heading out")

    def test_the_look_a_deck_sets_for_all_its_pages_is_kept_in_a_deck_of_its_own(self) -> None:
        """⚠ 見た目は案件に 1 つなので、既定の見た目の資料は、別の見た目が頁に何をするかを守れない。"""
        from pptx_agent_maker.layout.tokens import BAND_LOOKS, BAR_LOOKS, BOX_HEIGHTS, CARD_LOOKS, TABLE_LOOKS
        main = _toml(CORPUS / "workspace.toml").get("theme", {})
        looks = {key: {main.get(key)} | {_toml(path).get("theme", {}).get(key) for path in DECKS}
                 for key in ("card_look", "bar_look", "band_look", "box_height", "table_look")}
        for key, options in (("card_look", CARD_LOOKS), ("bar_look", BAR_LOOKS), ("band_look", BAND_LOOKS),
                             ("box_height", BOX_HEIGHTS), ("table_look", TABLE_LOOKS)):
            with self.subTest(key):
                self.assertEqual(set(options), {value or options[0] for value in looks[key]},
                                 f"{key}: a look no project of the corpus is set in")

    def test_the_cards_of_a_deck_in_the_outlined_look_say_what_the_look_does_to_them(self) -> None:
        written = [card for path in DECKS for manifest in (path.parent / "manifests").glob("*.toml")
                   for page in _toml(manifest)["pages"] for card in tables(page)
                   if card and set(card) <= set(CARD_KEYS)]
        self.assertEqual(set(CARD_KEYS) - {"icon"}, set(CARD_KEYS) & {key for card in written for key in card})
        self.assertTrue(any(not card.get("heading") and card.get("body") for card in written), "no card of words only")
        self.assertTrue(any(card.get("heading") and not card.get("body") and not card.get("tag") for card in written),
                        "no card of a heading only")
        self.assertTrue(any(not card.get("heading") and not card.get("body") for card in written), "no empty card")

    def test_a_row_that_divides_a_table_is_written_in_every_look_with_a_tone_and_without_one(self) -> None:
        """A band may be written whatever the look of the tables, so each look of the corpus has its own."""
        decks = {"the main project": CORPUS / "manifests",
                 **{path.parent.name: path.parent / "manifests" for path in DECKS}}
        for name, folder in decks.items():
            with self.subTest(name):
                bands = [row for manifest in sorted(folder.glob("*.toml")) for page in _toml(manifest)["pages"]
                         for row in tables(page) if "band" in row]
                self.assertTrue(any(row.get("tone") for row in bands), f"{name}: no band says its tone")
                self.assertTrue(any(not row.get("tone") for row in bands), f"{name}: every band says its tone")

    def test_every_role_a_use_of_the_project_sizes_apart_from_the_others(self) -> None:
        uses = _toml(CORPUS / "workspace.toml")["theme"]["uses"]
        self.assertEqual(set(), set(DERIVED) - {key for use in uses.values() for key in use})

    def test_every_height_a_band_may_have_and_every_height_a_use_may_pick_for_its_boxes(self) -> None:
        from pptx_agent_maker.layout.tokens import BOX_HEIGHTS
        uses = [use for path in (CORPUS / "workspace.toml", *DECKS)
                for use in _toml(path).get("theme", {}).get("uses", {}).values()]
        spacing = {key for use in uses for key in use.get("spacing", {})}
        self.assertEqual({"band_height", "conclusion_height"}, {"band_height", "conclusion_height"} & spacing)
        self.assertEqual(set(BOX_HEIGHTS), {use["box_height"] for use in uses if "box_height" in use})
        pages = [page for manifest in MANIFESTS for page in _toml(manifest)["pages"]]
        named = {use for use, body in ((page.get("use"), page) for page in pages) if use}
        self.assertEqual(set(), {name for path in (CORPUS / "workspace.toml", *DECKS)
                                 for name, use in _toml(path).get("theme", {}).get("uses", {}).items()
                                 if "box_height" in use or "band_height" in use.get("spacing", {})} - named)

    def test_every_look_a_use_may_pick_for_its_tables_in_a_deck_whose_tables_are_another(self) -> None:
        """A use's look of tables is told apart from the deck's only where the two differ, so each look is picked by a
        use in a project whose tables are the other one."""
        from pptx_agent_maker.layout.tokens import TABLE_LOOKS
        pages = [page for manifest in MANIFESTS for page in _toml(manifest)["pages"]]
        named = {page["use"] for page in pages if "use" in page}
        picked = set()
        for path in (CORPUS / "workspace.toml", *DECKS):
            theme = _toml(path).get("theme", {})
            deck = theme.get("table_look", TABLE_LOOKS[0])
            for name, use in theme.get("uses", {}).items():
                if "table_look" in use:
                    self.assertIn(name, named, f"{path.parent.name}: the use {name!r} is named by no page")
                    self.assertNotEqual(deck, use["table_look"], f"{name!r} picks the look its deck has")
                    picked.add(use["table_look"])
        self.assertEqual(set(TABLE_LOOKS), picked)

    def test_every_key_that_rules_a_picture_and_every_gap_a_use_sets_apart(self) -> None:
        """A picture is ruled in the default colour and in one asked for; a use sets the gap across and the gap down."""
        figures = [cell for cell in CELLS if "figure" in cell and "guides" in cell]
        self.assertEqual({"guides", "guide_tone"}, {key for cell in figures for key in cell} & {"guides", "guide_tone"})
        self.assertTrue(any("guide_tone" not in cell for cell in figures), "no picture is ruled in the default colour")
        self.assertTrue(any("caption" in cell for cell in figures), "no ruled picture carries a name")
        uses = _toml(CORPUS / "workspace.toml")["theme"]["uses"]
        apart = [name for name, use in uses.items() if {"gap_x", "gap_y", "band_gap"} <= set(use.get("spacing", {}))]
        self.assertTrue(apart, "no use sets the gap across, the gap down and the gap under a band")
        self.assertEqual(set(apart), {page.get("use") for page in DECLARED} & set(apart))

    def test_every_place_a_picture_may_stand_in_its_cell(self) -> None:
        from pptx_agent_maker.layout.types.bodies.compose import VALIGNS
        self.assertEqual(set(VALIGNS), {cell["valign"] for cell in CELLS if "figure" in cell and "valign" in cell})

    def test_a_row_of_cells_with_no_words(self) -> None:
        rows = [row for page in DECLARED if page["type"] == "compose" for row in page["rows"]]
        self.assertTrue(any(all("text" in cell and not cell["text"].strip() for cell in row["cells"]) for row in rows),
                        "no row is empty from end to end")

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
