"""Building a deck out of pages that already exist.

    archive.py   部品を触る最下層 (= pptx は zip)
    slides.py    テンプレートの複製 / 過去デッキからの輸入
    text.py      文言の置換

⚠ **宣言しなかった頁は、閉じるときに消える。**旧世代では「表示から外す」だけで部品が
残り、それが PowerPoint の修復ダイアログの主因だった。掃除を呼ぶ手順にすると忘れるので、
**残す頁を宣言する**形にしてある ― 宣言が順序であり、宣言されなかったものは消える。
"""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import slides as _slides
from . import text as _text
from .archive import Archive
from .text import ReplacementMissed

__all__ = ["Deck", "Slide", "ReplacementMissed", "build"]


def build(workspace, manifest):
    """Assemble the deck a manifest describes (= `deck.build.build`)."""
    from .build import build as _build

    return _build(workspace, manifest)


class Slide:
    """One page in the deck being built."""

    def __init__(self, archive: Archive, name: str) -> None:
        self._archive = archive
        self.name = name

    @property
    def path(self) -> Path:
        return self._archive.slide(self.name)

    def replace(self, old: str, new: str, *, count: int = 1) -> "Slide":
        """Swap exact words. Missing text raises rather than passing silently."""
        _text.replace(self.path, old, new, count=count)
        return self

    def words(self) -> list[str]:
        """Every run on the page — what `replace` can match."""
        return _text.words(self.path)

    def drop_marks(self) -> int:
        """Remove call-out boxes that came with an imported page."""
        return _text.drop_annotation_marks(self.path)


class Deck:
    """A deck assembled from a specimen, page by page."""

    def __init__(self, archive: Archive) -> None:
        self._archive = archive
        self._pages: list[Slide] = []

    @classmethod
    @contextmanager
    def open(cls, specimen: Path | str, destination: Path | str) -> Iterator["Deck"]:
        """Unpack a specimen deck, hand it over, then write out what was declared."""
        specimen, destination = Path(specimen), Path(destination)
        with tempfile.TemporaryDirectory() as workdir:
            archive = Archive.unpack(specimen, Path(workdir) / "unpacked")
            deck = cls(archive)
            yield deck
            deck._settle()
            archive.pack(destination)

    def copy(self, page_number: int) -> Slide:
        """Duplicate the specimen's Nth page (= reading order, 1-based)."""
        order = self._archive.order_of()
        if not 1 <= page_number <= len(order):
            raise IndexError(f"the specimen has {len(order)} pages; asked for {page_number}")
        page = Slide(self._archive, _slides.duplicate(self._archive, order[page_number - 1]))
        self._pages.append(page)
        return page

    def bring(self, source: Path | str, page_number: int,
              relayout: bool = False) -> Slide:
        """Import the Nth page of another deck, media and all.

        `relayout` は宣言で組んだ頁を持ち込むとき (= 白紙に描いてあるので、テンプレートの
        どのレイアウトの上に乗るかを引き継がせない)。過去デッキからの輸入では偽 ―
        その頁は元のレイアウトの上で作られている。
        """
        page = Slide(self._archive, _slides.import_from(self._archive, Path(source), page_number,
                                                        relayout=relayout))
        page.drop_marks()
        self._pages.append(page)
        return page

    @property
    def pages(self) -> list[Slide]:
        """The pages declared so far, in the order they will read."""
        return list(self._pages)

    def _settle(self) -> None:
        """Keep what was declared, in the order declared; remove everything else."""
        if not self._pages:
            raise ValueError("a deck with no pages is not a deck")
        kept = [page.name for page in self._pages]
        for name in self._archive.slide_names():
            if name not in kept:
                self._archive.unregister_slide(name)
        self._archive.set_order(kept)
        self._archive.drop_unreferenced_media()
