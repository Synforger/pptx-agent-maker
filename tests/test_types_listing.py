"""`types` lists what a manifest may say, read from the code itself."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402


class ListingTheTypes(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = create(Path(self.tmp.name) / "project")
        (self.root / "recipes.toml").write_text(
            '[recipes.result]\ntype = "figure"\ntitle = "{method} の結果"\n', encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _listing(self) -> str:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["types", str(self.root)]), 0)
        return out.getvalue()

    def test_every_registered_type_and_extra_is_listed(self) -> None:
        said = self._listing()
        for name in types.names():
            self.assertIn(f"  {name} ", said)
        for key in types.EXTRA_KEYS:
            self.assertIn(key, said)

    def test_the_projects_recipes_are_listed_with_their_holes(self) -> None:
        said = self._listing()
        self.assertIn("result", said)
        self.assertIn("fill: method", said)


if __name__ == "__main__":
    unittest.main()
