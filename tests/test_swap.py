"""New pictures and table cells on a page someone arranged by hand.

輸入した頁の形はそのままに、中身だけを新しくする。指すのは頁の上の並び順
(= 上の段から、同じ段は左から)。数や形が合わなければ止まり、古い絵は file に残らない。
"""

from __future__ import annotations

import io
import shutil
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.checks.rules import untyped_parts  # noqa: E402
from pptx_agent_maker.deck.swap import Box, reading_order  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
CM = 360000


def arranged_by_hand(destination: Path) -> Path:
    """Three pictures and a table, placed the way a person would in PowerPoint.

    上の段の 2 枚は、左の絵を 0.3mm 低くしてある (= 手で並べると揃わない)。上端だけで
    並べると、右の絵が先に来る。
    """
    deck = Presentation()
    deck.slide_width, deck.slide_height = Emu(12192000), Emu(6858000)
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    wide = str(DATA / "wide.png")
    slide.shapes.add_picture(wide, Emu(12 * CM), Emu(1 * CM), Emu(8 * CM), Emu(4 * CM))
    slide.shapes.add_picture(wide, Emu(1 * CM), Emu(1 * CM + 3000), Emu(8 * CM), Emu(4 * CM))
    slide.shapes.add_picture(wide, Emu(1 * CM), Emu(8 * CM), Emu(8 * CM), Emu(4 * CM))
    # PowerPoint が保存した絵は、絵の中に拡張情報を持つ (= `a:ext` という同じ名前が、位置より
    # 先に現れる)。実物のデッキでこれを位置と読んで落ちたので、見本にも入れておく。
    from lxml import etree
    blip = slide.shapes[0]._element.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
    blip.append(etree.fromstring(
        '<a:extLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:ext uri="{28A0092B-C50C-407E-A947-70E740481C1C}"/></a:extLst>'))
    table = slide.shapes.add_table(2, 2, Emu(12 * CM), Emu(8 * CM), Emu(8 * CM), Emu(3 * CM)).table
    for r, row in enumerate([["手法", "値"], ["A", "1"]]):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    deck.save(str(destination))
    return destination


class TheReadingOrder(unittest.TestCase):

    def test_a_row_is_read_left_to_right_even_when_it_is_not_level(self) -> None:
        right = (Box(12 * CM, CM, 8 * CM, 4 * CM), "right")
        left = (Box(1 * CM, CM + 3000, 8 * CM, 4 * CM), "left")
        below = (Box(1 * CM, 8 * CM, 8 * CM, 4 * CM), "below")
        self.assertEqual(reading_order([below, right, left]), ["left", "right", "below"])


class SwappingThroughTheBuild(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        create(self.root)
        arranged_by_hand(self.root / "w0.pptx")
        for name in ("dot.png", "wide.png"):
            shutil.copy(DATA / name, self.root / "assets" / name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _manifest(self, extra: str) -> None:
        (self.root / "w1.toml").write_text(
            'specimen = "specimen.pptx"\nout = "w1.pptx"\n\n[[pages]]\nkind = "import"\n'
            f'deck = "w0.pptx"\npage = 1\n{extra}\n', encoding="utf-8")

    def _run(self, *argv: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def _build(self) -> tuple[int, str]:
        return self._run("build", str(self.root), "w1")

    def test_pictures_go_in_by_reading_order_and_keep_their_shape(self) -> None:
        self._manifest('pictures = ["dot.png", "wide.png", "dot.png"]')
        code, said = self._build()
        self.assertEqual(code, 0, said)
        built = self.root / "w1.pptx"
        slide = Presentation(str(built)).slides[0]
        pics = {(round(s.left / CM), round(s.top / CM)): s for s in slide.shapes
                if s.shape_type == 13}
        dot, wide = (DATA / "dot.png").read_bytes(), (DATA / "wide.png").read_bytes()
        # 上の段の左 / 右 / 下の段 (= 並び順) に、渡した順で入る
        top_left = next(s for (x, y), s in pics.items() if x < 10 and y < 6)
        top_right = next(s for (x, y), s in pics.items() if x >= 10)
        bottom = next(s for (x, y), s in pics.items() if y >= 6)
        self.assertEqual(top_left.image.blob, dot)
        self.assertEqual(top_right.image.blob, wide)
        self.assertEqual(bottom.image.blob, dot)
        # 正方形の絵は 8 x 4 cm の枠の中央に 4 x 4 cm で収まる (= 潰れない)
        self.assertAlmostEqual(top_left.width / top_left.height, 1.0, places=2)
        self.assertLessEqual(top_left.width, 8 * CM)
        self.assertEqual(top_left.left + top_left.width // 2, 1 * CM + 4 * CM)
        self.assertEqual(untyped_parts.run(built), [])

    def test_the_old_pictures_do_not_travel_in_the_file(self) -> None:
        self._manifest('pictures = ["dot.png", "dot.png", "dot.png"]')
        self.assertEqual(self._build()[0], 0)
        wide = (DATA / "wide.png").read_bytes()
        with zipfile.ZipFile(self.root / "w1.pptx") as archive:
            media = [archive.read(n) for n in archive.namelist() if n.startswith("ppt/media/")]
        self.assertNotIn(wide, media, "a picture nobody shows is still inside the file")

    def test_table_cells_are_replaced_and_keep_the_shape(self) -> None:
        self._manifest('tables = [[["手法", "値"], ["B", "2"]]]')
        code, said = self._build()
        self.assertEqual(code, 0, said)
        slide = Presentation(str(self.root / "w1.pptx")).slides[0]
        table = next(s for s in slide.shapes if s.has_table).table
        self.assertEqual([[c.text for c in row.cells] for row in table.rows],
                         [["手法", "値"], ["B", "2"]])

    def test_the_wrong_number_of_pictures_stops_the_build(self) -> None:
        self._manifest('pictures = ["dot.png", "dot.png"]')
        code, said = self._build()
        self.assertEqual(code, 1)
        self.assertIn("has 3 pictures and 2 were given", said)
        self.assertFalse((self.root / "w1.pptx").exists())

    def test_a_table_of_another_shape_stops_the_build(self) -> None:
        self._manifest('tables = [[["手法", "値"], ["A", "1"], ["B", "2"]]]')
        code, said = self._build()
        self.assertEqual(code, 1)
        self.assertIn("another page", said)

    def test_a_key_an_imported_page_does_not_read_is_refused(self) -> None:
        """⚠ 型を通らない頁は、ここで拒まないと綴り違いがそのまま消える。"""
        self._manifest('picture = ["dot.png"]')
        code, said = self._build()
        self.assertEqual(code, 1)
        self.assertIn("does not take picture", said)

    def test_show_lists_the_page_in_the_order_it_is_filled(self) -> None:
        code, said = self._run("show", str(self.root), "w0.pptx:1")
        self.assertEqual(code, 0, said)
        lines = [line for line in said.splitlines() if line.strip().startswith(("1.", "2.", "3."))]
        self.assertIn("at (1.0, 1.0)", lines[0])
        self.assertIn("at (12.0, 1.0)", lines[1])
        self.assertIn("at (1.0, 8.0)", lines[2])
        self.assertIn("first row: 手法 | 値", said)


if __name__ == "__main__":
    unittest.main()
