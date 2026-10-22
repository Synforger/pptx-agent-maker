"""Words reach the contrast floor on every ground the toolkit paints, and a template's brand pairs pass by name.

⚠ **中ほどの濃さの差し色には、墨も紙も届かない。**差し色 2E9E5B の表の濃い段 (= 62B684) に墨 424242 が
乗って比 4.1、差し色そのものの段に紙 FFFFFF で 3.4。字の色は、届くまで黒か白へ寄せる。
⚠ **下限は字の大きさと太さで選ぶ。**大きい字 (= 18pt 以上、太字は 14pt 以上) は 3 で足りるので、3 に届く紙の色は
暗い色へ変えない。
⚠ **ブランドの差し色は、組で通す。**差し色の地に白い字は、テンプレートの側では動かせない。検査ごと外すと
灰色の字の取りこぼしも見えなくなるので、通してよい字の色と地の色の組を案件が書き、通した組は報告に出す。
⚠ **検査で通した組は、組む時も寄せない。**組だけで通す検査と、寄せて組む側が別の扱いをすると、型で組んだ表だけ
見た目が変わる。字の色は、選んだ色とその地の組が通す組に在れば、そのまま置く (= 向きが逆の組は寄せる)。
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
from dataclasses import replace
from types import SimpleNamespace
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from checks.test_checks import raw_deck, text_at  # noqa: E402

from pptx.dml.color import RGBColor  # noqa: E402
from pptx.util import Pt  # noqa: E402

from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.checks import report, run_all, run_built  # noqa: E402
from pptx_agent_maker.checks.rules import contrast as check  # noqa: E402
from pptx_agent_maker.layout.tokens import (  # noqa: E402
    READABLE, READABLE_LARGE, Palette, ThemeError, allowed_pairs, contrast, reading_floor, theme_from)
from pptx_agent_maker.project import create  # noqa: E402

BRAND = Palette(ink="424242", paper="FFFFFF", accent="2E9E5B")
#: 白い字を差し色の地に、差し色の字を白い地に (= どちらも 4.5 に届かない)
WHITE_ON_BRAND = {"words": "FFFFFF", "ground": "2E9E5B"}
PAIR_TOML = '{ words = "FFFFFF", ground = "2E9E5B" }'
#: 普通の字の大きさ (= 4.5 で数える。18pt 以上と、太字の 14pt 以上は 3)
BODY = 12.0
#: 組んだ資料で字の色を見る語と、その字が載る地 (= 表の見出し行・濃い段のセル・箱・期間の帯・棒・矢羽根)
WORDS_ON = {"段": BRAND.accent, "71%": BRAND.shade(3), "札A": BRAND.accent, "本文B": BRAND.accent,
            "上期": BRAND.accent, "作業": BRAND.accent, "終": BRAND.accent}


class WordsOnEveryShade(unittest.TestCase):
    def test_every_shade_of_the_accent_takes_words_that_reach_the_floor(self) -> None:
        for level in range(Palette.SHADES + 1):
            ground = BRAND.shade(level)
            with self.subTest(level=level, ground=ground):
                self.assertGreaterEqual(contrast(ground, BRAND.words_on(ground, BODY)), READABLE)

    def test_a_ground_the_ink_already_reaches_keeps_the_ink(self) -> None:
        for level in (0, 1, 2):
            with self.subTest(level=level):
                self.assertEqual(BRAND.ink, BRAND.words_on(BRAND.shade(level), BODY))

    def test_the_words_move_only_as_far_as_the_floor(self) -> None:
        """The deep shade's ink goes a little darker, not to black: one step less would not reach."""
        ground = BRAND.shade(3)
        words = BRAND.words_on(ground, BODY)
        self.assertNotIn(words, (BRAND.ink, "000000"))
        lighter = "".join(f"{int(words[i:i + 2], 16) + 1:02X}" for i in (0, 2, 4))
        self.assertLess(contrast(ground, lighter), READABLE)

    def test_when_the_paper_is_already_white_the_ink_moves_instead(self) -> None:
        """On the accent itself the paper reads better than the ink, but no white is whiter."""
        words = BRAND.words_on(BRAND.accent, BODY)
        self.assertLess(contrast(BRAND.accent, BRAND.paper), READABLE)
        self.assertGreaterEqual(contrast(BRAND.accent, words), READABLE)
        self.assertLess(int(words[:2], 16), int(BRAND.ink[:2], 16), "the ink was not taken toward black")

    def test_the_floor_follows_the_size_and_weight_of_the_words(self) -> None:
        """The check and the palette read one rule: 18pt and bold 14pt are large, and an unwritten size is large."""
        for points, bold, floor in ((12, False, READABLE), (12, True, READABLE), (13.9, True, READABLE),
                                    (14, True, READABLE_LARGE), (14, False, READABLE), (17.9, False, READABLE),
                                    (18, False, READABLE_LARGE), (None, False, READABLE_LARGE)):
            with self.subTest(points=points, bold=bold):
                self.assertEqual(floor, reading_floor(points, bold))

    def test_large_words_that_reach_the_large_floor_keep_the_paper(self) -> None:
        """White on the accent is 3.4: too faint at 12pt, enough for a bold heading or for 18pt."""
        self.assertGreaterEqual(contrast(BRAND.accent, BRAND.paper), READABLE_LARGE)
        self.assertNotEqual(BRAND.paper, BRAND.words_on(BRAND.accent, BODY))
        for points, bold in ((14, True), (18, False), (24, True), (None, False)):
            with self.subTest(points=points, bold=bold):
                self.assertEqual(BRAND.paper, BRAND.words_on(BRAND.accent, points, bold))
        self.assertNotEqual(BRAND.paper, BRAND.words_on(BRAND.accent, 13.9, True))
        self.assertNotEqual(BRAND.paper, BRAND.words_on(BRAND.accent, 14, False))

    def test_large_words_on_the_deep_shade_keep_the_ink(self) -> None:
        """The ink is 4.1 on the deep shade: it moves at 12pt, and stays at 18pt."""
        ground = BRAND.shade(3)
        self.assertNotEqual(BRAND.ink, BRAND.words_on(ground, BODY))
        self.assertEqual(BRAND.ink, BRAND.words_on(ground, 18))

    def _built_words(self, theme: str, allowed: str = "") -> dict[str, tuple[str, float, bool]]:
        """(colour, points, bold) of the words each caller sets on the accent (or its deep shade), as written.

        `allowed` is what the project writes under `[checks]` (= the pairs it lets through).
        """
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "project"
            create(root)
            settings = root / "workspace.toml"
            text = settings.read_text(encoding="utf-8")
            if allowed:
                text = text.replace("\n[checks]\n", f"\n[checks]\n{allowed}\n")
            settings.write_text(text + f'\n[theme]\n{theme}\n[theme.palette]\nink = "424242"\npaper = "FFFFFF"\n'
                                'accent = "2E9E5B"\n', encoding="utf-8")
            (root / "w1.toml").write_text('''specimen = "specimen.pptx"
out = "w1.pptx"

[[pages]]
kind = "declare"
type = "board"
title = "濃さの表"
table = [["段", "値"], ["3", { text = "71%", shade = 3 }]]
footer = "出所"

[[pages]]
kind = "declare"
type = "cards"
title = "差し色の箱"
cards = [{ heading = "札A", tone = "accent" }, { heading = "札B", body = "本文B", tone = "accent" }]

[[pages]]
kind = "declare"
type = "timeline"
title = "期間の帯は差し色"
periods = ["上期", "下期"]
lanes = [{ name = "担当", tone = "accent", bars = [{ text = "作業", from = 1, to = 2 }] }]

[[pages]]
kind = "declare"
type = "roadmap"
title = "道のり"
stages = [{ name = "始", nodes = [["一", "甲"]] }, { name = "終", goal = true, nodes = [["二", "乙"]] }]
''', encoding="utf-8")
            said = io.StringIO()
            with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
                code = main(["build", str(root), "w1"])
            self.assertEqual(0, code, said.getvalue())
            self.assertRegex(said.getvalue(), r"(ok|pass)\s+contrast" if allowed else r"ok\s+contrast")
            with zipfile.ZipFile(root / "w1.pptx") as deck:
                xml = "".join(deck.read(n).decode() for n in deck.namelist() if n.startswith("ppt/slides/slide"))
        built = {}
        for words in (*WORDS_ON, "札B"):
            run = re.search(r'<a:r>(<a:rPr[^>]*>(?:(?!</a:rPr>).)*?<a:srgbClr val="(\w{6})"(?:(?!</a:r>).)*?)'
                            rf'<a:t>{words}</a:t>', xml, re.S)
            properties = re.match(r"<a:rPr[^>]*>", run.group(1)).group(0)
            built[words] = (run.group(2), int(re.search(r'\bsz="(\d+)"', properties).group(1)) / 100,
                            'b="1"' in properties)
        return built

    def test_every_caller_gives_the_words_their_own_size_and_weight(self) -> None:
        """Whatever size and weight a caller wrote the words in, their colour is the palette's for exactly those.

        Read (body 12), presented (body 18), a read deck with its body at 15pt and one with its stages at
        20pt: the same pages, and white stays on the accent exactly where the words are large. A box's two kinds of words share one colour, the
        smaller words' (= the body's).
        """
        for theme in ('use = "read"', 'use = "present"', 'use = "read"\n[theme.type]\nbody = 15',
                      'use = "read"\n[theme.type]\nstage = 20'):
            built = self._built_words(theme)
            for words, ground in WORDS_ON.items():
                colour, points, bold = built[words]
                with self.subTest(theme=theme, words=words, points=points, bold=bold):
                    self.assertEqual(BRAND.words_on(ground, points, bold), colour)
            self.assertEqual(built["本文B"][0], built["札B"][0], theme)

    def test_a_heading_row_in_large_type_keeps_white_and_in_small_type_goes_dark(self) -> None:
        """The presented deck sets its body at 18pt, the read deck at 12pt: white stays only where it reads."""
        large, small = self._built_words('use = "present"'), self._built_words('use = "read"')
        self.assertEqual((BRAND.paper, BRAND.ink), (large["段"][0], large["71%"][0]))
        self.assertNotEqual(BRAND.paper, small["段"][0])
        self.assertEqual(BRAND.paper, small["札A"][0], "a heading of 16pt bold is large")

    def test_a_pair_the_project_lets_through_is_set_as_it_is_not_moved(self) -> None:
        """White on the accent is let through by the check: the heading row of a table keeps the paper's colour."""
        kept = self._built_words('use = "read"', f"contrast_allowed = [{PAIR_TOML}]")
        for words in ("段", "札A", "上期"):
            with self.subTest(words=words):
                self.assertEqual(BRAND.paper, kept[words][0])
        unlisted = self._built_words('use = "read"')
        self.assertNotEqual(BRAND.paper, unlisted["段"][0], "without the pair the heading row still moves")

    def test_only_the_pair_in_its_own_direction_is_kept(self) -> None:
        """The pair the other way round, or another pair on the same ground, leaves the words moving."""
        for written in ('{ words = "2E9E5B", ground = "FFFFFF" }', '{ words = "424242", ground = "2E9E5B" }',
                        '{ words = "FFFFFF", ground = "62B684" }'):
            with self.subTest(written=written):
                moved = self._built_words('use = "read"', f"contrast_allowed = [{written}]")
                self.assertNotEqual(BRAND.paper, moved["段"][0])

    def test_a_pair_is_kept_only_on_the_ground_it_names(self) -> None:
        """The deep shade is another ground: the words on it still move to the floor."""
        kept = self._built_words('use = "read"', f"contrast_allowed = [{PAIR_TOML}]")
        self.assertEqual(BRAND.words_on(BRAND.shade(3), 12.0), kept["71%"][0])
        self.assertNotEqual(BRAND.paper, kept["71%"][0])

    def test_the_palette_keeps_what_is_let_through_and_nothing_else(self) -> None:
        """`words_on` keeps the colour it chose when the pair is let through, and moves the rest as before."""
        allowing = replace(BRAND, allowed=allowed_pairs({"contrast_allowed": [WHITE_ON_BRAND]}))
        self.assertEqual(BRAND.paper, allowing.words_on(BRAND.accent, BODY))
        self.assertEqual(BRAND.paper, allowing.words_on(BRAND.accent, BODY, True))
        for ground in (BRAND.shade(3), BRAND.shade(2)):
            self.assertEqual(BRAND.words_on(ground, BODY), allowing.words_on(ground, BODY))
        other_ground = "38A062"  # the paper reads best here too, and still falls short of the floor
        self.assertNotEqual(BRAND.paper, allowing.words_on(other_ground, BODY))
        self.assertEqual(BRAND.words_on(other_ground, BODY), allowing.words_on(other_ground, BODY))
        other_words = replace(BRAND, allowed=allowed_pairs({"contrast_allowed": [
            {"words": "FFFFFF", "ground": BRAND.shade(3)}]}))
        self.assertEqual(BRAND.words_on(BRAND.shade(3), BODY), other_words.words_on(BRAND.shade(3), BODY),
                         "the ink is what was chosen on that ground: the pair names the paper")
        backwards = replace(BRAND, allowed=allowed_pairs({"contrast_allowed": [{"words": "2E9E5B", "ground": "FFFFFF"}]}))
        self.assertEqual(BRAND.words_on(BRAND.accent, BODY), backwards.words_on(BRAND.accent, BODY))

    def test_the_project_cannot_let_a_pair_through_from_the_palette(self) -> None:
        with self.assertRaises(ThemeError):
            theme_from({"palette": {"allowed": "FFFFFF"}})

    def test_the_build_and_the_check_read_the_pairs_in_one_way(self) -> None:
        """A pair written with a hash and in lower case is kept by the build and passed by the check."""
        written = '{ words = "#ffffff", ground = "2e9e5b" }'
        kept = self._built_words('use = "read"', f"contrast_allowed = [{written}]")
        self.assertEqual(BRAND.paper, kept["段"][0])
        self.assertEqual((("FFFFFF", "2E9E5B"),), allowed_pairs({"contrast_allowed": [{"words": "#ffffff",
                                                                                      "ground": "2e9e5b"}]}))

    def test_a_shaded_table_built_on_that_accent_is_not_called_faded(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "project"
            create(root)
            settings = root / "workspace.toml"
            settings.write_text(settings.read_text(encoding="utf-8")
                                + '\n[theme.palette]\nink = "424242"\npaper = "FFFFFF"\naccent = "2E9E5B"\n',
                                encoding="utf-8")
            (root / "w1.toml").write_text('''specimen = "specimen.pptx"
out = "w1.pptx"

[[pages]]
kind = "declare"
type = "board"
title = "濃さの表"
table = [["段", "値"], ["1", { text = "12%", shade = 1 }], ["3", { text = "71%", shade = 3 }],
         ["4", { text = "96%", shade = 4 }]]
footer = "出所"
''', encoding="utf-8")
            said = io.StringIO()
            with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
                main(["build", str(root), "w1"])
            self.assertIn("ok    contrast", said.getvalue())
            with zipfile.ZipFile(root / "w1.pptx") as deck:
                xml = "".join(deck.read(n).decode() for n in deck.namelist() if n.startswith("ppt/slides/slide"))
            for words in ("71%", "96%"):
                colour = re.search(r'<a:r><a:rPr[^>]*>(?:(?!</a:rPr>).)*?<a:srgbClr val="(\w{6})"(?:(?!</a:r>).)*?'
                                   rf'<a:t>{words}</a:t>', xml, re.S)
                self.assertEqual(BRAND.words_on(BRAND.shade(3 if words == "71%" else 4), BODY), colour.group(1))


class PairsLetThrough(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _deck(self, name: str, *boxes: tuple[str, str]) -> Path:
        """One page with a box of 14pt words per (words, ground)."""
        def place(slide):
            for number, (words, ground) in enumerate(boxes):
                box = text_at(slide, f"字 {number}", left=Pt(20 + 200 * number), size=Pt(14))
                box.fill.solid()
                box.fill.fore_color.rgb = RGBColor.from_string(ground)
                box.text_frame.paragraphs[0].runs[0].font.color.rgb = RGBColor.from_string(words)
        return raw_deck(self.dir / name, place)

    def test_a_pair_the_project_names_passes_and_is_said(self) -> None:
        deck = self._deck("brand.pptx", ("FFFFFF", "2E9E5B"), ("FFFFFF", "2E9E5B"))
        self.assertTrue(check.run(deck, {}), "white on the accent should fall short of the floor")
        found = run_all(deck, {"contrast_allowed": [WHITE_ON_BRAND]})
        self.assertFalse([f for f in found if f.check == check.NAME])
        said = report(found)
        self.assertRegex(said, r"pass\s+contrast\s+#FFFFFF on #2E9E5B \(contrast 3\.4\): 2 places on page 1")
        self.assertIn("contrast_allowed", said)

    def test_only_the_pair_passes_not_either_colour(self) -> None:
        """The same two colours the other way round, and grey on white, are still called."""
        deck = self._deck("others.pptx", ("2E9E5B", "FFFFFF"), ("8A8A8A", "FFFFFF"), ("FFFFFF", "2E9E5B"))
        found = check.run(deck, {"contrast_allowed": [WHITE_ON_BRAND]})
        self.assertEqual(["#2E9E5B on #FFFFFF", "#8A8A8A on #FFFFFF"],
                         sorted(re.search(r"#\w+ on #\w+", f.what).group(0) for f in found))
        self.assertEqual(1, len(found.allowed))

    def test_a_pair_is_written_with_or_without_the_hash_in_either_case(self) -> None:
        deck = self._deck("hash.pptx", ("FFFFFF", "2E9E5B"))
        self.assertFalse(check.run(deck, {"contrast_allowed": [{"words": "#ffffff", "ground": "2e9e5b"}]}))

    def test_a_build_reports_what_it_let_through_too(self) -> None:
        deck = self._deck("built.pptx", ("FFFFFF", "2E9E5B"))
        found = run_built(deck, SimpleNamespace(entries=[]), None, {"contrast_allowed": [WHITE_ON_BRAND]})
        self.assertRegex(report(found, declared=True), r"pass\s+contrast\s+#FFFFFF on #2E9E5B")

    def test_a_pair_that_is_not_two_colours_is_refused(self) -> None:
        deck = self._deck("bad.pptx", ("FFFFFF", "2E9E5B"))
        for written in ("FFFFFF", ["FFFFFF", "2E9E5B"], [{"words": "FFFFFF"}], [{"words": "white", "ground": "2E9E5B"}],
                        [{"words": "FFFFFF", "ground": 0x2E9E5B}]):
            with self.subTest(written=written), self.assertRaises(ValueError) as refused:
                check.run(deck, {"contrast_allowed": written})
            self.assertIn("contrast_allowed", str(refused.exception))

    def test_a_clean_report_says_nothing_was_let_through(self) -> None:
        deck = self._deck("clean.pptx", ("1A1A1A", "FFFFFF"))
        found = run_all(deck, {"contrast_allowed": [WHITE_ON_BRAND]})
        self.assertNotIn("pass", report(found))

    def test_the_project_settings_reach_the_check(self) -> None:
        """`[checks] contrast_allowed` in workspace.toml is what `check` reads."""
        root = self.dir / "project"
        create(root)
        settings = root / "workspace.toml"
        text = settings.read_text(encoding="utf-8")
        self.assertIn("\n[checks]\n", text)
        settings.write_text(text.replace("\n[checks]\n", '\n[checks]\ncontrast_allowed = [\n'
                                         '  { words = "FFFFFF", ground = "2E9E5B" },\n]\n'), encoding="utf-8")
        self._deck("imported.pptx", ("FFFFFF", "2E9E5B"), ("8A8A8A", "FFFFFF"))
        (self.dir / "imported.pptx").rename(root / "imported.pptx")
        said = io.StringIO()
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            code = main(["check", str(root), "imported"])
        self.assertEqual(1, code, said.getvalue())
        self.assertIn("#8A8A8A on #FFFFFF", said.getvalue())
        self.assertNotIn("#FFFFFF on #2E9E5B  <-", said.getvalue())
        self.assertRegex(said.getvalue(), r"pass\s+contrast\s+#FFFFFF on #2E9E5B")


if __name__ == "__main__":
    unittest.main()
