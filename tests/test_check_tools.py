"""The two tools a refactor is checked with have to catch what they are for.

⚠ **効かない番人は、緑のまま素通しする。**snapshot は「1 バイトも変わっていない」を、mutate は
「test が見張っている」を言うための道具で、どちらも黙って通す側に壊れると誰も気づかない。
ここでは、変えた物・増えた頁・test が見ていない壊し方・古くなった表を、わざと作って渡す。
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / "tests" / "corpus" / "assets"


def _tool(name: str):
    """One of the scripts under scripts/check/ (= not importable as a package)."""
    spec = importlib.util.spec_from_file_location(f"check_{name}", REPO / "scripts" / "check" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


snapshot = _tool("snapshot")
mutate = _tool("mutate")

PAGE = """
[[pages]]
kind = "declare"
type = "board"
title = "{title}"
table = [["Key", "Value"], ["a", "1"]]
"""


def quietly(run, *argv: str) -> tuple[int, str]:
    said = io.StringIO()
    with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
        code = run(list(argv))
    return code, said.getvalue()


class ASnapshot(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.corpus = self.root / "corpus"
        (self.corpus / "manifests").mkdir(parents=True)
        self._write("One page")

    def _write(self, *titles: str) -> None:
        (self.corpus / "manifests" / "deck.toml").write_text(
            'specimen = "specimen.pptx"\nout = "deck.pptx"\n'
            + "".join(PAGE.format(title=title) for title in titles), encoding="utf-8")

    def _baked(self, name: str) -> Path:
        out = self.root / name
        snapshot.bake(self.corpus, out)
        return out

    def test_baking_the_same_corpus_twice_gives_the_same_files(self) -> None:
        self.assertEqual([], snapshot.differences(self._baked("first"), self._baked("second")))

    def test_a_page_is_kept_with_what_it_points_at(self) -> None:
        kept = sorted(path.name for path in (self._baked("first") / "deck").iterdir())
        self.assertEqual(["page-01.rels", "page-01.xml"], kept)

    def test_one_changed_word_is_found_and_the_page_is_named(self) -> None:
        before = self._baked("before")
        self._write("One pagf")
        found = snapshot.differences(before, self._baked("after"))
        self.assertEqual(1, len(found), found)
        self.assertIn("changed  deck/page-01.xml", found[0])
        self.assertIn("One pagf", found[0], "the line that differs is not the one shown")

    def test_a_picture_swapped_for_another_of_the_same_shape_is_found(self) -> None:
        """⚠ **頁は絵を名前でしか指さない。**同じ縦横比の絵を取り違えても、XML は 1 字も変わらない。"""
        (self.corpus / "assets").mkdir()
        shutil.copy(ASSETS / "circle.png", self.corpus / "assets" / "shape.png")
        (self.corpus / "manifests" / "deck.toml").write_text(
            'specimen = "specimen.pptx"\nout = "deck.pptx"\n'
            '[[pages]]\nkind = "declare"\ntype = "figure"\ntitle = "x"\nfigure = "shape.png"\n',
            encoding="utf-8")
        before = self._baked("before")
        shutil.copy(ASSETS / "square.png", self.corpus / "assets" / "shape.png")
        after = self._baked("after")
        self.assertEqual((before / "deck" / "page-01.xml").read_text(encoding="utf-8"),
                         (after / "deck" / "page-01.xml").read_text(encoding="utf-8"),
                         "the two pictures are not the same shape, so this proves nothing")
        found = snapshot.differences(before, after)
        self.assertEqual(1, len(found), found)
        self.assertIn("changed  deck/page-01.rels", found[0])

    def test_a_page_added_and_a_page_dropped_are_both_named(self) -> None:
        one = self._baked("one")
        self._write("One page", "Another")
        two = self._baked("two")
        self.assertTrue(any(line.startswith("new      deck/page-02.xml")
                            for line in snapshot.differences(one, two)))
        self.assertTrue(any(line.startswith("missing  deck/page-02.xml")
                            for line in snapshot.differences(two, one)))

    def test_checking_fails_until_the_snapshot_is_kept_and_again_once_a_page_moves(self) -> None:
        corpus = ("--corpus", str(self.corpus))
        code, said = quietly(snapshot.main, *corpus, "--check")
        self.assertEqual(1, code, "nothing is kept yet, and the check passed")
        self.assertIn("new      deck/page-01.xml", said)

        self.assertEqual(0, quietly(snapshot.main, *corpus)[0])
        self.assertEqual(0, quietly(snapshot.main, *corpus, "--check")[0])

        self._write("A page that moved")
        code, said = quietly(snapshot.main, *corpus, "--check")
        self.assertEqual(1, code, "a page changed, and the check passed")
        self.assertIn("1 differ", said)

    def test_keeping_twice_leaves_one_snapshot_and_nothing_else(self) -> None:
        corpus = ("--corpus", str(self.corpus))
        quietly(snapshot.main, *corpus)
        quietly(snapshot.main, *corpus)
        self.assertEqual(0, quietly(snapshot.main, *corpus, "--check")[0])
        self.assertEqual(["deck"], sorted(path.name for path in (self.corpus / "snapshot").iterdir()))

    def test_a_corpus_that_does_not_build_stops_instead_of_keeping_less(self) -> None:
        (self.corpus / "manifests" / "deck.toml").write_text(
            'specimen = "specimen.pptx"\nout = "deck.pptx"\n'
            '[[pages]]\nkind = "declare"\ntype = "not_a_type"\ntitle = "x"\n', encoding="utf-8")
        code, said = quietly(snapshot.main, "--corpus", str(self.corpus))
        self.assertEqual(1, code)
        self.assertIn("not_a_type", said)
        self.assertFalse((self.corpus / "snapshot").exists(), "a failed bake left a snapshot behind")


SOURCE = '''def double(x):
    return x * 2


def nobody_calls_this():
    return 1
'''

TESTS = '''import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from thing import double


class Doubling(unittest.TestCase):
    def test_every_number(self):
        for number in (1, 2, 3):
            with self.subTest(number):
                self.assertEqual(double(number), number + number)
'''

ALWAYS_RED = '''import unittest


class Broken(unittest.TestCase):
    def test_that_was_red_before_anything_was_broken(self):
        self.fail("red in the baseline")
'''

NOTICED = mutate.Mutant("the result is tripled", "src/thing.py", "x * 2", "x * 3")
UNNOTICED = mutate.Mutant("a function nobody calls", "src/thing.py", "return 1", "return 2")
STALE = mutate.Mutant("code that is no longer there", "src/thing.py", "x * 4", "x * 5")
UNIMPORTABLE = mutate.Mutant("the module no longer imports", "src/thing.py", "def double(x):", "def double(x:")


class Mutating(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "src" / "thing.py").write_text(SOURCE, encoding="utf-8")
        (self.root / "tests" / "test_thing.py").write_text(TESTS, encoding="utf-8")
        self.said: list[str] = []

    def _mutate(self, *mutants, tests=("tests/test_thing.py",)) -> int:
        return mutate.mutate(self.root, list(tests), list(mutants), say=self.said.append)

    def _line(self, mutant) -> str:
        return next(line for line in self.said if mutant.name in line)

    def test_a_mutant_only_a_subtest_notices_is_red(self) -> None:
        self.assertEqual(0, self._mutate(NOTICED))
        self.assertIn("red", self._line(NOTICED))

    def test_a_mutant_no_test_notices_is_reported_and_counted(self) -> None:
        self.assertEqual(1, self._mutate(NOTICED, UNNOTICED))
        self.assertIn("GREEN", self._line(UNNOTICED))
        self.assertIn("red", self._line(NOTICED))

    def test_a_mutant_that_no_longer_applies_is_counted_and_the_rest_still_run(self) -> None:
        """⚠ 壊せない壊し方を黙って飛ばすと、表は古くなっていくのに「全部赤」と言い続ける。"""
        self.assertEqual(1, self._mutate(STALE, NOTICED))
        self.assertIn("cannot break", self._line(STALE))
        self.assertIn("red", self._line(NOTICED))

    def test_a_string_found_twice_is_not_guessed_at(self) -> None:
        twice = mutate.Mutant("which one?", "src/thing.py", "return", "return 0 or")
        self.assertEqual(1, self._mutate(twice))
        self.assertIn("2 times", self._line(twice))

    def test_what_was_red_before_does_not_make_a_mutant_red(self) -> None:
        (self.root / "tests" / "test_broken.py").write_text(ALWAYS_RED, encoding="utf-8")
        both = ("tests/test_thing.py", "tests/test_broken.py")
        self.assertEqual(1, self._mutate(UNNOTICED, NOTICED, tests=both))
        self.assertIn("baseline: 1 red", self.said[0])
        self.assertIn("GREEN", self._line(UNNOTICED))
        self.assertIn("red", self._line(NOTICED))

    def test_a_mutant_that_stops_the_tests_from_being_collected_is_red(self) -> None:
        """壊した結果が「test が落ちる」ではなく「test を集められない」でも、気づかれたことに変わりはない。"""
        self.assertEqual(0, self._mutate(UNIMPORTABLE))
        self.assertIn("red", self._line(UNIMPORTABLE))

    def test_the_tree_itself_is_left_as_it_was(self) -> None:
        self._mutate(NOTICED, UNNOTICED)
        self.assertEqual(SOURCE, (self.root / "src" / "thing.py").read_text(encoding="utf-8"))

    def test_tests_that_do_not_run_are_an_error_not_a_green(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "did not run the tests"):
            self._mutate(NOTICED, tests=("tests/test_that_is_not_there.py",))

    def test_a_table_is_refused_when_it_cannot_prove_anything(self) -> None:
        for body, why in [
            ('tests = ["t.py"]\n', "no [[mutant]]"),
            ('[[mutant]]\nname = "n"\nfile = "f"\nold = "a"\nnew = "b"\n', "`tests`"),
            ('tests = ["t.py"]\n[[mutant]]\nname = "n"\nfile = "f"\nold = "a"\nnew = "a"\n', "changes nothing"),
            ('tests = ["t.py"]\n[[mutant]]\nname = "n"\nfile = "f"\nold = "a"\n', "takes exactly"),
            ('test = ["t.py"]\n', "does not take test"),
        ]:
            with self.subTest(why):
                table = self.root / "table.toml"
                table.write_text(body, encoding="utf-8")
                with self.assertRaises(mutate.TableError) as caught:
                    mutate.load(table)
                self.assertIn(why, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
