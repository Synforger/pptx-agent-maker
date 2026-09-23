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

from pptx_agent_maker.deck.slides import _rename_media
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




class RenamingMediaNeverEatsItsOwnOutput(unittest.TestCase):
    """Renaming the pictures of an imported page must not chain.

    ⚠ **付け替えは 1 パスで行う。**1 つずつ置換すると、付けたばかりの名前が次の置換の
    **探す名前**になることがあり、そのときは前に置き換えた分も巻き込まれる ― 4 枚の絵を
    持つ頁を輸入したら 4 枚とも同じ 1 枚になった (= 焼いて初めて出た。頁の形はもっとも
    らしいままなので、絵を並べて見るまで気づけない)。どの順に処理されるかは set の
    並びしだいなので、通る日と壊れる日があった。
    """

    def test_a_rename_that_would_chain_is_done_in_one_pass(self):
        rels = ('<Relationship Id="rId1" Target="../media/image1.png"/>'
                '<Relationship Id="rId2" Target="../media/image2.png"/>')
        # image1 の行き先が image2 ― 1 つずつ置換すると、次に image2 を探した時点で
        # さっき置き換えたほうも道連れになる
        carried = {"image1.png": "image2.png", "image2.png": "image3.png"}
        moved = _rename_media(rels, carried)
        self.assertIn("../media/image2.png", moved)
        self.assertIn("../media/image3.png", moved)
        self.assertEqual(1, moved.count("image2.png"),
                         "two relationships ended up pointing at the same picture")
        self.assertEqual(1, moved.count("image3.png"))

    def test_a_name_nobody_renamed_is_left_alone(self):
        rels = '<Relationship Id="rId1" Target="../media/image9.png"/>'
        self.assertEqual(rels, _rename_media(rels, {}))


class ManyPicturesSurviveTheImport(unittest.TestCase):
    """A page with several images keeps them all — the names must not collide.

    ⚠ 絵を 1 枚ずつ番号の付け替えをしていた間は、付けた名前が次の付け替えの探す名前に
    なり、4 枚の絵が 4 枚とも同じ 1 枚になった。頁の形はもっともらしいままなので、
    焼いた絵を並べて見るまで気づけない。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _png(self, path: Path, width: int, height: int, rgb) -> Path:
        import struct, zlib
        raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

        def chunk(tag, data):
            body = tag + data
            return (struct.pack(">I", len(data)) + body
                    + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

        path.write_bytes(b"\x89PNG\r\n\x1a\n"
                         + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                         + chunk(b"IDAT", zlib.compress(raw))
                         + chunk(b"IEND", b""))
        return path

    def test_four_different_pictures_stay_four_different_pictures(self):
        import hashlib
        import zipfile
        from pptx_agent_maker.layout import Page, Rect
        from pptx_agent_maker.write import add_page, new_deck, save

        shades = [(10, 10, 10), (90, 90, 90), (170, 170, 170), (250, 250, 250)]
        sources = [self._png(self.root / f"p{index}.png", 8, 8, shade)
                   for index, shade in enumerate(shades)]
        wanted = {hashlib.sha1(path.read_bytes()).hexdigest() for path in sources}
        self.assertEqual(4, len(wanted), "the fixture itself must hold four different files")

        # ⚠ 先に絵を持つ頁を 1 枚入れておく ― 付け替え先の番号が、付け替え元の番号と
        # 重なる状況を作らないと、この欠陥は出ない (= 番号が重ならない見本では素通りする)
        deck = new_deck()
        first = Page("いちまい")
        first.figure(first.body, sources[0], 1.0)
        add_page(deck, first.build())

        page = Page("よんまい")
        for cell, source in zip([c for band in page.body.grid(2, 2, gap=0) for c in band],
                                sources):
            page.figure(cell, source, 1.0)
        add_page(deck, page.build())
        declared = save(deck, self.root / "declared.pptx")

        with Deck.open(declared, self.root / "out.pptx") as built:
            built.bring(declared, 1)
            built.bring(declared, 2)

        with zipfile.ZipFile(self.root / "out.pptx") as zipped:
            carried = {hashlib.sha1(zipped.read(name)).hexdigest()
                       for name in zipped.namelist() if name.startswith("ppt/media/")}
        self.assertEqual(wanted, carried,
                         "the imported page no longer holds the four pictures it was given")


class TheFixturesTravelWithTheRepository(unittest.TestCase):
    """The images the tests draw on must be tracked.

    ⚠ 案件の絵を持ち込ませないために画像は丸ごと無視してあり、そのぶん **test の見本まで
    一緒に落ちていた** ― 手元では通り、clone した先でだけ落ちる。
    """

    def test_every_image_under_tests_data_is_tracked(self):
        import subprocess
        root = Path(__file__).resolve().parents[1]
        on_disk = {p.name for p in (root / "tests" / "data").glob("*.png")}
        listed = subprocess.run(["git", "ls-files", "tests/data"], cwd=root,
                                capture_output=True, text=True, check=True)
        tracked = {Path(line).name for line in listed.stdout.split() if line.endswith(".png")}
        self.assertEqual(on_disk, tracked,
                         "a fixture image is not in the repository; a fresh clone cannot "
                         "run these tests")



class PicturesNobodyKeepsAreDropped(unittest.TestCase):
    """⚠ **頁を消しても、その頁の絵は残っていた。**

    部品を消すのは参照の側だけなので、載せなかった絵が最後まで運ばれる ― デッキが重く
    なるだけでなく、**載せないと決めた絵が納品物の中まで付いてくる**。実物では、頁を
    落として 1 頁にしたデッキの重さのほとんどが、誰からも参照されない絵だった。
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        # ⚠ 頁ごとに**別の**絵を持たせる (= 同じ 1 枚を共有していると、頁を落としても
        # その絵はまだ誰かに使われていて、掃除が効いたのか分からない)
        deck = new_deck()
        for title, picture in (("一枚目", "dot.png"), ("二枚目", "wide.png")):
            page = Page(title, footer="出所")
            page.figure(page.body, REPO / "tests" / "data" / picture, 1.0, caption=title)
            add_page(deck, page.build())
        self.specimen = save(deck, self.dir / "specimen.pptx")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def _media(deck: Path) -> set[str]:
        with zipfile.ZipFile(deck) as archive:
            return {Path(n).name for n in archive.namelist() if n.startswith("ppt/media/")}

    def test_the_pictures_of_a_page_nobody_declared_are_gone(self) -> None:
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            deck.copy(1)
        self.assertLess(len(self._media(out)), len(self._media(self.specimen)),
                        "誰からも参照されない絵が残っている")

    def test_the_picture_of_a_page_that_stayed_is_still_there(self) -> None:
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            deck.copy(1)
        with zipfile.ZipFile(out) as archive:
            rels = "".join(archive.read(n).decode("utf-8") for n in archive.namelist()
                           if n.endswith(".rels"))
        wanted = set(re.findall(r'media/([\w.]+)"', rels))
        self.assertTrue(wanted, "頁が絵を 1 枚も指していない")
        self.assertTrue(wanted <= self._media(out), "まだ使われている絵まで落ちている")

    def test_nothing_is_dropped_when_every_page_stays(self) -> None:
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            deck.copy(1)
            deck.copy(2)
        with zipfile.ZipFile(out) as archive:
            rels = "".join(archive.read(n).decode("utf-8") for n in archive.namelist()
                           if n.endswith(".rels"))
        self.assertTrue(set(re.findall(r'media/([\w.]+)"', rels)) <= self._media(out))



class DeclaredPagesDoNotInheritALayout(unittest.TestCase):
    """⚠ **宣言で組んだ頁は白紙に描いてある。**

    持ち込むときレイアウトの参照をそのままにすると、番号だけが引き継がれて型見本の別の
    レイアウトの上に乗る。実物では「終わりの頁」の上に乗り、その背景の飾りが全頁に出た。
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.specimen = a_specimen(self.dir / "specimen.pptx", ["表紙"])
        self.elsewhere = a_specimen(self.dir / "elsewhere.pptx", ["前の回", "その次"])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _layouts(self, deck: Path) -> list[str]:
        with zipfile.ZipFile(deck) as archive:
            return [found for name in archive.namelist() if name.startswith("ppt/slides/_rels/")
                    for found in re.findall(r"slideLayout\d+", archive.read(name).decode("utf-8"))]

    def test_a_declared_page_lands_on_the_first_layout(self) -> None:
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            deck.copy(1)
            deck.bring(self.elsewhere, 1, relayout=True)
        self.assertIn("slideLayout1", self._layouts(out))

    def test_a_page_imported_from_an_earlier_deck_keeps_its_own(self) -> None:
        """過去の回の頁は、元のレイアウトの上で作られている (= 動かさない)。"""
        out = self.dir / "built.pptx"
        with Deck.open(self.specimen, out) as deck:
            deck.copy(1)
            deck.bring(self.elsewhere, 2)
        with zipfile.ZipFile(self.elsewhere) as archive:
            rels = archive.read("ppt/slides/_rels/slide2.xml.rels").decode("utf-8")
        self.assertIn(re.findall(r"slideLayout\d+", rels)[0], self._layouts(out))


if __name__ == "__main__":
    unittest.main()
