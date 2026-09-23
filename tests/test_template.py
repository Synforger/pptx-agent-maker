"""The project template ships with real files, and they are the toolkit's own look.

⚠ **雛形が pptx を 1 枚も持たない間は、`init` した直後の案件で最初に出るのが
「型見本が無い」だった。**雛形は「写せば動く」ところまでを持つ。

⚠ **見本は `layout/tokens.py` から焼いた派生物**なので、色や書体を変えて焼き直しを
忘れると、複製した頁 (= 見本の意匠) と型で組んだ頁 (= tokens の意匠) が割れる。
ここがその番人で、鳴ったら `task specimen` を実行する。
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.deck.build import build  # noqa: E402
from pptx_agent_maker.layout.tokens import DEFAULT  # noqa: E402
from pptx_agent_maker.project import Workspace, create  # noqa: E402
from pptx_agent_maker.project.manifest import Manifest  # noqa: E402

TEMPLATE = REPO / "templates" / "project"
SPECIMEN = TEMPLATE / "specimen.pptx"
TASKFILE = TEMPLATE / "Taskfile.yml"
CLI = REPO / "src" / "pptx_agent_maker" / "__main__.py"


def _baker():
    """The script that bakes the template's files (= not importable as a package)."""
    spec = importlib.util.spec_from_file_location("baker", REPO / "scripts" / "bake-template.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TemplateFilesTest(unittest.TestCase):
    def test_the_template_carries_its_specimen(self) -> None:
        self.assertTrue(SPECIMEN.is_file(), f"{SPECIMEN} is missing — run task specimen")

    def test_the_template_carries_the_picture_its_example_points_at(self) -> None:
        manifest = (TEMPLATE / "example.toml").read_text(encoding="utf-8")
        for name in re.findall(r'figure = "([^"]+)"', manifest):
            self.assertTrue((TEMPLATE / "assets" / "example" / name).is_file(), name)

    def test_the_specimen_has_a_cover_to_copy(self) -> None:
        with zipfile.ZipFile(SPECIMEN) as archive:
            pages = [n for n in archive.namelist()
                     if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
        self.assertEqual(len(pages), 1, "the specimen is one cover, nothing else")

    def test_the_specimen_says_it_is_the_shape_it_is(self) -> None:
        """⚠ 寸法を変えても紙の種類の申告は既定のまま残る (= PowerPoint が別の寸法を言う)。"""
        with zipfile.ZipFile(SPECIMEN) as archive:
            presentation = archive.read("ppt/presentation.xml").decode("utf-8")
        self.assertIn(f'cx="{DEFAULT.slide.width}"', presentation)
        self.assertIn('type="screen16x9"', presentation)


class TheProjectCanCallTheToolkitTest(unittest.TestCase):
    """⚠ **案件の folder はそれ自体で完結していないといけない。**

    道具は folder の中に入らないので、入っていなければ「どの python に入っているか」を
    人が覚えている必要があった。`Taskfile.yml` がその口で、ここはそれが道具の動詞と
    食い違っていないかを見る (= CLI 側の名前を変えたら鳴る)。
    """

    @staticmethod
    def _verbs(text: str, pattern: str) -> set[str]:
        return set(re.findall(pattern, text))

    def test_the_template_carries_the_entry_point(self) -> None:
        self.assertTrue(TASKFILE.is_file(), "a project with no Taskfile cannot be used on its own")

    def test_every_command_of_the_toolkit_has_a_task(self) -> None:
        """`init` だけは案件が在る前の動詞なので、案件の口には無い。"""
        toolkit = self._verbs(CLI.read_text(encoding="utf-8"), r'add_parser\("(\w+)"')
        # ⚠ 呼び出しの行だけを見る (= 道具の名前は説明の文にも出てくる)。
        tasks = self._verbs(TASKFILE.read_text(encoding="utf-8"),
                            r"- '\{\{\.MAKER\}\} (\w+)")
        self.assertEqual(tasks, toolkit - {"init"})

    def test_the_toolkit_is_named_rather_than_run_as_a_module(self) -> None:
        """⚠ `python -m ...` で書くと、どの python かを案件が知る必要が出る。"""
        self.assertNotIn("python3 -m", TASKFILE.read_text(encoding="utf-8"))

    def test_a_missing_toolkit_is_said_plainly(self) -> None:
        text = TASKFILE.read_text(encoding="utf-8")
        self.assertIn("preconditions", text, "a missing toolkit should stop with a sentence")
        self.assertIn("not on PATH", text)


class TheSpecimenMatchesTheTokensTest(unittest.TestCase):
    """焼き直し忘れを止める ― 見本の意匠と道具の意匠は同じ 1 枚から来る。"""

    def setUp(self) -> None:
        with zipfile.ZipFile(SPECIMEN) as archive:
            self.theme = archive.read("ppt/theme/theme1.xml").decode("utf-8")

    def test_every_colour_in_the_master_comes_from_the_palette(self) -> None:
        """⚠ 一致は辞書どうしで見る (= 落ちたときテーマ全文が出ると誰も読まない)。"""
        scheme = re.search(r"<a:clrScheme.*?</a:clrScheme>", self.theme, re.S)
        self.assertIsNotNone(scheme, "the specimen has no colour scheme")
        found = dict(re.findall(r'<a:(\w+)><a:srgbClr val="([0-9A-F]{6})"/></a:\1>',
                                scheme.group(0)))
        self.assertEqual(found, {slot: getattr(DEFAULT.palette, name)
                                 for slot, name in _baker().SCHEME},
                         "the specimen drifted from tokens.py — run task specimen")

    def test_the_master_is_set_in_the_toolkits_typeface(self) -> None:
        families = set(re.findall(r'<a:latin typeface="([^"]*)"', self.theme))
        self.assertEqual(families, {DEFAULT.type.family}, "run task specimen")


class TheTemplateBuildsTest(unittest.TestCase):
    """⚠ **init した直後に 1 本焼けること** ― 雛形が本当に完結しているかはこれで決まる。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "a-project"
        create(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_example_builds_straight_out_of_init(self) -> None:
        workspace = Workspace.load(self.root)
        manifest = Manifest.load(workspace.manifest("example"))
        built = build(workspace, manifest)
        self.assertTrue(built.is_file())
        with zipfile.ZipFile(built) as archive:
            pages = [n for n in archive.namelist()
                     if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
        self.assertEqual(len(pages), len(manifest.entries))

    def test_the_project_is_laid_down_with_its_own_entry_point(self) -> None:
        self.assertTrue((self.root / "Taskfile.yml").is_file())

    def test_the_cover_is_reworded_by_the_example(self) -> None:
        workspace = Workspace.load(self.root)
        built = build(workspace, Manifest.load(workspace.manifest("example")))
        with zipfile.ZipFile(built) as archive:
            words = "".join(
                archive.read(n).decode("utf-8") for n in archive.namelist()
                if n.startswith("ppt/slides/slide") and n.endswith(".xml")
            )
        self.assertNotIn(_baker().TITLE, words, "the specimen's own words survived")


if __name__ == "__main__":
    unittest.main()
