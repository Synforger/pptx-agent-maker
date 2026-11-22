"""Draw the decks of a comparison as one picture per page, the way the live preview draws them.

LibreOffice makes the PDFs and pdftoppm the pictures, both found and started by the preview's own `render.py`.
Two things differ from the preview. The decks share one LibreOffice process, so they share its stand-in faces.
And the pictures are PNG, because a JPEG's blocks spread one changed pixel over its neighbours and the count of
differing pixels would stop being a count. `decks.py` calls this once per comparison.

呼ぶ前に、プレビューの部品が import できる所に在ること (= checkout のプレビューは `__main__` が道に載せる)。
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path

from PIL import Image
from pptx_live_preview.cache import cache_root
from pptx_live_preview.render import (DEFAULT_DPI, ProfilePool, RenderError, convert_to_pdfs, pdftoppm_bin,
                                      poppler_environment, prepare_deck)

#: 絵の細かさ。プレビューが本画像を焼くのと同じ (= 画面で見た頁と同じ絵を数える)
COMPARE_DPI = DEFAULT_DPI

#: LibreOffice のプロファイルの置き場。プレビューの物とは別にする (= 常駐のプレビューが同じ
#: プロファイルを掴んでいる間に変換すると、ロックがぶつかる)。変換は 1 本ずつなので 1 つで足りる
PROFILES = ProfilePool(lambda: cache_root() / "_libreoffice-compare", 1)

_PAGE_PICTURE = re.compile(r"-(\d+)\.png$")


def bake_decks(decks: Sequence[Path], work: Path) -> list[list[Path]]:
    """Each deck's pages as PNG files under `work`, in reading order (= hidden pages included).

    ⚠ **資料を 1 本ずつ別の process で変換しない。**LibreOffice は無い書体の代わりを process ごとに選ぶので、
    分けると、同じ資料でも字のある頁が全部違う絵になる。1 つの process は渡された順に 1 本ずつ変換する。
    """
    together = work / "converted"
    together.mkdir(parents=True, exist_ok=True)
    folders = [work / str(position) for position in range(len(decks))]
    copies = []
    for position, (deck, folder) in enumerate(zip(decks, folders)):
        folder.mkdir(exist_ok=True)
        # 前後の版は同じ file 名のことが多い。位置を頭に付けて、PDF の名前を分ける
        copy = together / f"{position}-{deck.stem}.pptx"
        shutil.copyfile(prepare_deck(deck, folder), copy)
        copies.append(copy)
    with PROFILES.lease() as profile:
        pdfs = convert_to_pdfs(copies, together, profile)
    return [_draw_pages(deck, pdf, folder) for deck, pdf, folder in zip(decks, pdfs, folders)]


def open_pages(pages: list[Path]) -> Iterator[Image.Image]:
    """The pictures one at a time, each closed again when the next is asked for."""
    for page in pages:
        with Image.open(page) as picture:
            yield picture


def _draw_pages(deck: Path, pdf: Path, work: Path) -> list[Path]:
    result = subprocess.run([pdftoppm_bin(), "-png", "-r", str(COMPARE_DPI), str(pdf), str(work / "page")],
                            capture_output=True, text=True, env=poppler_environment())
    if result.returncode != 0:
        raise RenderError(f"pdftoppm failed: {result.stderr.strip()}")
    pages = sorted(work.glob("page-*.png"), key=lambda path: int(_PAGE_PICTURE.search(path.name).group(1)))
    if not pages:
        raise RenderError(f"{deck.name} drew no pages")
    return pages
