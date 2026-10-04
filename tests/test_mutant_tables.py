"""The tables of mutants this repository keeps still fit the code they break.

⚠ **道具の test (= `test_check_tools.py`) と分けてある。**ここの test は、実装を 1 か所でも書き換えた
写しの中では必ず赤になる (= 表の `old` がその写しから消える)。道具を壊す表がここまで流すと、どの
壊し方も「赤」と数えられ、道具の test が見張っていない壊し方が隠れる。
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MUTANTS = REPO / "tests" / "mutants"


def _tool(name: str):
    """One of the scripts under scripts/check/ (= not importable as a package)."""
    spec = importlib.util.spec_from_file_location(f"check_{name}", REPO / "scripts" / "check" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mutate = _tool("mutate")


class TheTablesOfThisRepository(unittest.TestCase):
    def test_every_mutant_still_applies(self) -> None:
        """⚠ **file を動かしたり書き換えたりすると、表の `file` と `old` が古くなる。**全部を流すのは
        重いので、ここでは「今の実装にちょうど 1 か所当たる」ことだけを見る。"""
        tables = sorted(MUTANTS.glob("*.toml"))
        self.assertTrue(tables, "no tables under tests/mutants")
        for table in tables:
            tests, mutants = mutate.load(table)
            for test in tests:
                self.assertTrue((REPO / test).is_file(), f"{table.name}: no test at {test}")
            for mutant in mutants:
                with self.subTest(table=table.name, mutant=mutant.name):
                    source = REPO / mutant.file
                    self.assertTrue(source.is_file(), f"no file at {mutant.file}")
                    self.assertEqual(1, source.read_text(encoding="utf-8").count(mutant.old))

    def test_the_example_goes_red_all_the_way_through(self) -> None:
        said: list[str] = []
        tests, mutants = mutate.load(MUTANTS / "_example.toml")
        self.assertEqual(0, mutate.mutate(REPO, tests, mutants, say=said.append), "\n".join(said))
        self.assertIn("baseline: 0 red", said[0])


if __name__ == "__main__":
    unittest.main()
