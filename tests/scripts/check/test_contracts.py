"""Every test file is in the table of promises, and every row names a target and a test file that exist.

The check (`scripts/check/contracts.py`) is run the way `task ci` runs it, on small repositories made here: one
that agrees with its table, and ones broken in each way the check is there to see.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CHECK = REPO / "scripts" / "check" / "contracts.py"


def _check(root: Path) -> subprocess.CompletedProcess[str]:
    """Run the check on `root` and keep what it printed."""
    return subprocess.run([sys.executable, str(CHECK), "--root", str(root)], capture_output=True, text=True)


class TheCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.root / "src").mkdir()
        (self.root / "tests" / "area").mkdir(parents=True)
        (self.root / "tests" / "area" / "test_one.py").write_text("", encoding="utf-8")
        self.table = self.root / "tests" / "contracts.txt"
        self.table.write_text("# a comment\n\nsrc | tests/area/test_one.py | One thing is kept.\n", encoding="utf-8")

    def test_a_table_that_agrees_passes(self) -> None:
        result = _check(self.root)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("0 problem(s)", result.stdout)

    def test_a_test_no_row_names_is_told(self) -> None:
        (self.root / "tests" / "area" / "test_two.py").write_text("", encoding="utf-8")
        result = _check(self.root)
        self.assertEqual(1, result.returncode)
        self.assertIn("tests/area/test_two.py: no row", result.stdout)

    def test_a_row_whose_test_or_target_is_gone_is_told(self) -> None:
        with self.table.open("a", encoding="utf-8") as table:
            table.write("gone | tests/area/test_gone.py | Something no longer here.\n")
        result = _check(self.root)
        self.assertEqual(1, result.returncode)
        self.assertIn("the target gone does not exist", result.stdout)
        self.assertIn("the test tests/area/test_gone.py does not exist", result.stdout)

    def test_a_row_with_no_promise_or_the_wrong_fields_is_told(self) -> None:
        with self.table.open("a", encoding="utf-8") as table:
            table.write("src | tests/area/test_one.py |\nsrc | tests/area/test_one.py\n")
        result = _check(self.root)
        self.assertEqual(1, result.returncode)
        self.assertIn("says no promise", result.stdout)
        self.assertIn("this one has 2", result.stdout)


class ThisRepository(unittest.TestCase):
    def test_its_table_names_every_test_and_nothing_that_is_gone(self) -> None:
        result = _check(REPO)
        self.assertEqual(0, result.returncode, result.stdout)


if __name__ == "__main__":
    unittest.main()
