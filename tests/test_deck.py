"""Copying a specimen page and importing one from an earlier deck.

⚠ ここで守るのは、旧世代で実際に壊れた 3 つ ―
**宣言しなかった頁の部品が残る** (= 修復ダイアログの主因)、
**置換の空振りが黙って通る**、**複製が元の絵を共有する**。
"""

from __future__ import annotations

import re
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker import DEFAULT, Page  # noqa: E402
from pptx_agent_maker.deck import Deck, ReplacementMissed  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402


def a_specimen(destination: Path, titles: list[str]) -> Path:
    """A small deck to copy from, built with the declarative layer."""
    deck = new_deck()
    for title in titles:
        page = Page(title, condition=f"{title} の条件", footer="出所")
        left, right = page.body.columns(2, gap=DEFAULT.spacing.gap_m)
        page.figure(left, REPO / "tests" / "data" / "dot.png", 1.0, caption=f"{title} の図")
        page.table(right, [["列", "値"], ["A", "1"]])
        add_page(deck, page.build())
    return save(deck, destination)


def make_dot() -> Path:
    """A tiny PNG written on the spot, so a specimen has media to copy."""
    target = REPO / "tests" / "data" / "dot.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    if True:  # written every run: a half-written fixture otherwise fails forever
        raw = b"".join(b"\x00" + b"\x80\x80\x80" * 8 for _ in range(8))
        def chunk(tag: bytes, payload: bytes) -> bytes:
            body = tag + payload
            return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))
        target.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )
    return target


class DeckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        make_dot()

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.specimen = a_specimen(self.dir / "specimen.pptx", ["一枚目", "二枚目", "三枚目"])
        self.earlier = a_specimen(self.dir / "earlier.pptx", ["過去の頁"])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _parts(self, deck: Path) -> list[str]:
        with zipfile.ZipFile(deck) as archive:
            return [n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]

    def _order(self, deck: Path) -> list[str]:
        with zipfile.ZipFile(deck) as archive:
            presentation = archive.read("ppt/presentation.xml").decode()
            rels = archive.read("ppt/_rels/presentation.xml.rels").decode()
        file_of = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"', rels))
        return [file_of[r] for r in re.findall(r'r:id="(rId\d+)"', presentation) if r in file_of]

    def test_a_copied_page_carries_the_specimen_text(self) -> None:
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            page = deck.copy(2)
            self.assertIn("二枚目", page.words())

    def test_replacing_changes_the_words(self) -> None:
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            page = deck.copy(2).replace("二枚目", "新しい見出し")
            self.assertIn("新しい見出し", page.words())
            self.assertNotIn("二枚目", page.words())

    def test_a_replacement_that_misses_raises(self) -> None:
        """A silent miss leaves a page nobody edited, found only when it is read."""
        out = self.dir / "built.pptx"
        with self.assertRaises(ReplacementMissed):
            with Deck.open(self.specimen, out) as deck:
                deck.copy(1).replace("そんな文字は無い", "x")

    def test_only_the_declared_pages_survive(self) -> None:
        """The specimen's own pages must be gone — parts, not just hidden."""
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            deck.copy(3)
            deck.copy(1)
        self.assertEqual(len(self._parts(out)), 2, "an undeclared page kept its part")
        self.assertEqual(len(self._order(out)), 2)

    def test_pages_read_in_the_order_they_were_declared(self) -> None:
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            third, first = deck.copy(3), deck.copy(1)
        self.assertEqual(self._order(out), [third.name, first.name])

    def test_an_imported_page_comes_with_its_media(self) -> None:
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            deck.copy(1)
            brought = deck.bring(self.earlier, 1)
            self.assertIn("過去の頁", brought.words())
        with zipfile.ZipFile(out) as archive:
            images = [n for n in archive.namelist() if n.startswith("ppt/media/")]
        self.assertGreaterEqual(len(images), 2, "the imported page lost its picture")

    def test_a_copy_gets_its_own_media(self) -> None:
        """Two copies of one page must not share a picture, or editing one changes both."""
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            first, second = deck.copy(1), deck.copy(1)
            media = []
            for page in (first, second):
                rels = (page.path.parent / "_rels" / f"{page.name}.rels").read_text()
                media.append(set(re.findall(r'media/(image[\w.]+)', rels)))
        self.assertTrue(media[0].isdisjoint(media[1]), "the two copies share a media part")

    def test_a_deck_with_no_pages_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            with Deck.open(self.specimen, self.dir / "empty.pptx"):
                pass

    def test_the_built_deck_converts(self) -> None:
        """LibreOffice reading it end to end is the closest check to opening it."""
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            deck.copy(1).replace("一枚目", "差し替えた見出し")
            deck.bring(self.earlier, 1)
        result = subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf", str(out), "--outdir", str(self.dir)],
            capture_output=True, timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode()[:400])
        self.assertTrue((self.dir / "built.pdf").is_file(), "the deck did not convert")


if __name__ == "__main__":
    unittest.main()
