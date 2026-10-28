"""Draw a deck as one picture per page, the way the live preview draws it.

LibreOffice makes the PDF and pdftoppm the pictures, both found and started by the preview's own `render.py`;
the only difference is the file type, PNG here, because a JPEG's blocks spread one changed pixel over its
neighbours and the count of differing pixels would stop being a count. `decks.py` calls this once per deck.

呼ぶ前に、プレビューの部品が import できる所に在ること (= checkout のプレビューは `__main__` が道に載せる)。
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

from PIL import Image
from pptx_live_preview.cache import cache_root
from pptx_live_preview.render import (DEFAULT_DPI, ProfilePool, RenderError, pdftoppm_bin, poppler_environment,
                                      to_pdf)

#: 絵の細かさ。プレビューが本画像を焼くのと同じ (= 画面で見た頁と同じ絵を数える)
COMPARE_DPI = DEFAULT_DPI

#: LibreOffice のプロファイルの置き場。プレビューの物とは別にする (= 常駐のプレビューが同じ
#: プロファイルを掴んでいる間に変換すると、ロックがぶつかる)。変換は 1 本ずつなので 1 つで足りる
PROFILES = ProfilePool(lambda: cache_root() / "_libreoffice-compare", 1)

_PAGE_PICTURE = re.compile(r"-(\d+)\.png$")


def bake_pages(deck: Path, work: Path) -> list[Path]:
    """The deck's pages as PNG files under `work`, in reading order (= hidden pages included)."""
    work.mkdir(parents=True, exist_ok=True)
    with PROFILES.lease() as profile:
        pdf = to_pdf(deck, work, profile)
    result = subprocess.run([pdftoppm_bin(), "-png", "-r", str(COMPARE_DPI), str(pdf), str(work / "page")],
                            capture_output=True, text=True, env=poppler_environment())
    if result.returncode != 0:
        raise RenderError(f"pdftoppm failed: {result.stderr.strip()}")
    pages = sorted(work.glob("page-*.png"), key=lambda path: int(_PAGE_PICTURE.search(path.name).group(1)))
    if not pages:
        raise RenderError(f"{deck.name} drew no pages")
    return pages


def open_pages(pages: list[Path]) -> Iterator[Image.Image]:
    """The pictures one at a time, each closed again when the next is asked for."""
    for page in pages:
        with Image.open(page) as picture:
            yield picture
