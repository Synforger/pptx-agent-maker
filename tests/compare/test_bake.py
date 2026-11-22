"""Both decks of a comparison are drawn by one LibreOffice process, so they get the same stand-in face.

`soffice` and `pdftoppm` are stood in for, so these run on a machine without them: the stand-in soffice draws
differently in each process, the way LibreOffice does when a deck names a typeface the machine lacks. A deck here
is a text file with one line for each of its pages.
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "preview" / "src"))

from pptx_agent_maker.compare import compare_decks  # noqa: E402
from pptx_live_preview.render import RenderError  # noqa: E402

#: `soffice` の代わり。起動ごとに違う印を全部の頁に付ける。「broken」の資料は、成功の code のまま PDF を作らない
FAKE_SOFFICE = """#!{python}
import sys
import uuid
from pathlib import Path

face = uuid.uuid4().hex
at = sys.argv.index("--outdir")
out = Path(sys.argv[at + 1])
for deck in map(Path, sys.argv[at + 2:]):
    words = deck.read_text()
    if "broken" not in words:
        (out / (deck.stem + ".pdf")).write_text("".join(face + line + "\\n" for line in words.splitlines()))
"""

#: `pdftoppm` の代わり。1 行を 1 頁とし、行の中身で色の決まる絵にする
FAKE_PDFTOPPM = """#!{python}
import hashlib
import sys
from pathlib import Path
from PIL import Image

for number, line in enumerate(Path(sys.argv[-2]).read_text().splitlines(), 1):
    colour = tuple(hashlib.sha256(line.encode()).digest()[:3])
    Image.new("RGB", (8, 6), colour).save(f"{{sys.argv[-1]}}-{{number}}.png")
"""


class DrawingBothDecksInOneProcess(unittest.TestCase):

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        programs = self.folder / "bin"
        programs.mkdir()
        for name, source in (("soffice", FAKE_SOFFICE), ("pdftoppm", FAKE_PDFTOPPM)):
            program = programs / name
            program.write_text(source.format(python=sys.executable), encoding="utf-8")
            program.chmod(program.stat().st_mode | stat.S_IXUSR)
        patch = mock.patch.dict(os.environ, {"PATH": f"{programs}{os.pathsep}{os.environ['PATH']}",
                                             "XDG_CACHE_HOME": str(self.folder / "cache")})
        patch.start()
        self.addCleanup(patch.stop)

    def _deck(self, name: str, *pages: str) -> Path:
        deck = self.folder / name
        deck.parent.mkdir(parents=True, exist_ok=True)
        deck.write_text("".join(f"{page}\n" for page in pages), encoding="utf-8")
        return deck

    def test_a_deck_compared_with_itself_differs_nowhere_although_each_process_draws_differently(self) -> None:
        deck = self._deck("deck.pptx", "one", "two", "three")
        self.assertEqual([page.is_changed for page in compare_decks(deck, deck)], [False, False, False])

    def test_only_the_edited_page_differs(self) -> None:
        before, after = self._deck("before.pptx", "one", "two", "three"), self._deck("after.pptx", "one", "2", "three")
        self.assertEqual([page.is_changed for page in compare_decks(before, after)], [False, True, False])

    def test_two_versions_with_one_file_name_do_not_overwrite_each_other(self) -> None:
        before, after = self._deck("old/w1.pptx", "one", "two"), self._deck("new/w1.pptx", "one", "2")
        self.assertEqual([page.is_changed for page in compare_decks(before, after)], [False, True])

    def test_the_decks_keep_their_sides(self) -> None:
        before, after = self._deck("before.pptx", "one", "two"), self._deck("after.pptx", "one")
        last = compare_decks(before, after)[-1]
        self.assertIsNotNone(last.before_size)
        self.assertIsNone(last.after_size)

    def test_each_deck_is_numbered_as_powerpoint_prints_it_before_it_is_drawn(self) -> None:
        def numbered(deck: Path, work_dir: Path) -> Path:
            copy = work_dir / "numbered" / deck.name
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_text(deck.read_text(encoding="utf-8").replace("field", "printed"), encoding="utf-8")
            return copy

        before, after = self._deck("old/w1.pptx", "field"), self._deck("new/w1.pptx", "printed")
        with mock.patch("pptx_live_preview.render.numbered_as_powerpoint", numbered):
            self.assertEqual([page.is_changed for page in compare_decks(before, after)], [False])

    def test_a_deck_that_gave_no_pdf_is_named_although_soffice_ended_with_0(self) -> None:
        before, after = self._deck("before.pptx", "one"), self._deck("spoilt.pptx", "broken")
        with self.assertRaisesRegex(RenderError, "expected pdf not produced.*spoilt"):
            compare_decks(before, after)


if __name__ == "__main__":
    unittest.main()
