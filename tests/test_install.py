"""Installing the toolkit installs the live preview with it.

⚠ **プレビューを別の package として配っていた間、checkout の外に入れたツールの `preview` は
`No module named 'pptx_live_preview'` で落ちた。**repo から動かしたとき (= editable) だけ、
`__main__.py` が checkout の `preview/src` を path に足して動いていた。ツールの wheel が
プレビューも包んでいることを、配る宣言から見る。
"""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
PREVIEW = "pptx_live_preview"


def _setuptools() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["setuptools"]


def _package_dir(name: str) -> Path | None:
    """Where the toolkit's package search finds a package (= a folder with `__init__.py`)."""
    for where in _setuptools()["packages"]["find"]["where"]:
        folder = REPO / where / name
        if (folder / "__init__.py").is_file():
            return folder
    return None


class ThePreviewTravelsWithTheToolkitTest(unittest.TestCase):
    def test_the_package_search_finds_the_preview(self) -> None:
        self.assertIsNotNone(_package_dir(PREVIEW),
                             "the preview is outside the toolkit's package search, "
                             "so an installed toolkit has no preview")

    def test_the_page_the_preview_serves_is_declared_as_package_data(self) -> None:
        """⚠ `.py` でない file は宣言しないと wheel に入らない (= 画面の html・css・js が抜ける)。"""
        folder = _package_dir(PREVIEW)
        self.assertIsNotNone(folder)
        globs = _setuptools().get("package-data", {}).get(PREVIEW, [])
        shipped = {path for pattern in globs for path in folder.glob(pattern) if path.is_file()}
        assets = {path for path in (folder / "assets").rglob("*") if path.is_file()}
        self.assertTrue(assets, "the preview has no page to serve")
        self.assertEqual(assets - shipped, set(), "a file the preview serves is left out of the wheel")


if __name__ == "__main__":
    unittest.main()
