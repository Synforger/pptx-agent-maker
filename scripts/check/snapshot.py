"""Bake every manifest of the corpus and keep its slide XML, to tell a refactor from a change.

作り直し (= file を動かす、関数を割る) は「動きを変えない」と言って入れるが、test が緑でも
頁が 1 EMU 動いていることがある ― test は書いた人が思いついた所しか見ていない。ここは見本
(= `tests/corpus/`) を焼き、頁の XML をそのまま残す。作り直しの前後で 1 バイトでも違えば、
それは作り直しではなく変更。

    snapshot.py            焼いて、残してある XML (= tests/corpus/snapshot/) を書き直す
    snapshot.py --check    焼いて、残してある XML と比べる (= 違えば終了コード 1)

⚠ **道具の中身を import しない。**通るのは利用者と同じ入口 (= `init` と `build`) だけ。
中の module を直に呼ぶと、その module を動かす作り直しのたびにここも直すことになり、
比べる側と比べられる側が一緒に動く。

⚠ **案件は repo の外に建てる** (= 中の案件は道具が拒む)。見本は一時の置き場へ写してから焼く。
"""

from __future__ import annotations

import argparse
import contextlib
import filecmp
import hashlib
import io
import re
import shutil
import sys
import tempfile
import time
import tomllib
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.__main__ import main as toolkit  # noqa: E402

CORPUS = REPO / "tests" / "corpus"
KEPT = CORPUS / "snapshot"

#: 違いを見せるときの 1 行の長さ (= 図形 1 つの XML は長いので、頭だけ出す)
SHOWN = 160

_ORDER = re.compile(r'<p:sldId[^>]*r:id="(rId\d+)"')
_SLIDE = re.compile(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"')
_MEDIA = re.compile(r'Target="\.\./media/([^"]+)"')


class SnapshotError(RuntimeError):
    """The corpus could not be baked."""


def bake(corpus: Path, out: Path) -> list[Path]:
    """Build every manifest of `corpus` in a project of its own and write each page's XML under `out`.

    頁は読む順に `page-NN.xml` (+ その頁が指す物と絵の digest の `page-NN.rels`)、グラフは `chartN.xml`。
    """
    manifests = sorted((corpus / "manifests").glob("*.toml"))
    if not manifests:
        raise SnapshotError(f"no manifests under {corpus / 'manifests'}")
    written: list[Path] = []
    with tempfile.TemporaryDirectory() as scratch:
        project = Path(scratch) / "project"
        _run("init", str(project))
        for name in ("workspace.toml", "recipes.toml"):
            if (corpus / name).is_file():
                shutil.copy2(corpus / name, project / name)
        for manifest in manifests:
            shutil.copy2(manifest, project / manifest.name)
        if (corpus / "assets").is_dir():
            shutil.copytree(corpus / "assets", project / "assets", dirs_exist_ok=True)
        # 名前の順に焼く (= 前の manifest が焼いた deck から、後の manifest が頁を輸入できる)
        for manifest in manifests:
            _run("build", str(project), manifest.stem)
            with manifest.open("rb") as handle:
                deck = project / str(tomllib.load(handle)["out"])
            written += _pages(deck, out / manifest.stem)
    return written


def _run(*argv: str) -> str:
    """One of the toolkit's commands, as a person would run it; what it said, or why it stopped."""
    said, complained = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(said), contextlib.redirect_stderr(complained):
        code = toolkit(list(argv))
    if code:
        raise SnapshotError(f"`{' '.join(argv[:1] + argv[-1:])}` stopped with {code}:\n"
                            f"{said.getvalue()}{complained.getvalue()}")
    return said.getvalue()


def _pages(deck: Path, out: Path) -> list[Path]:
    """Each page of a built deck, in reading order, one element to a line."""
    out.mkdir(parents=True, exist_ok=True)
    written = []
    with zipfile.ZipFile(deck) as archive:
        file_of = dict(_SLIDE.findall(archive.read("ppt/_rels/presentation.xml.rels").decode("utf-8")))
        order = [file_of[rid] for rid in _ORDER.findall(archive.read("ppt/presentation.xml").decode("utf-8"))
                 if rid in file_of]
        for number, slide in enumerate(order, start=1):
            written.append(_keep(out / f"page-{number:02d}.xml", archive.read(f"ppt/slides/{slide}")))
            rels = f"ppt/slides/_rels/{slide}.rels"
            if rels in archive.namelist():
                written.append(_keep(out / f"page-{number:02d}.rels", _with_digests(archive, rels)))
        for name in sorted(archive.namelist()):
            if re.fullmatch(r"ppt/charts/chart\d+\.xml", name):
                written.append(_keep(out / Path(name).name, archive.read(name)))
    return written


def _with_digests(archive: zipfile.ZipFile, rels: str) -> bytes:
    """A page's relationships, each picture followed by a digest of the file it names.

    ⚠ **絵は名前でしか指されていない** (= `../media/image1.png`)。同じ形の絵を取り違えても、頁の
    XML も指す名前も変わらない ― 中身の digest を並べて、初めて「同じ絵」と言える。
    """
    xml = archive.read(rels).decode("utf-8")
    for target in sorted(set(_MEDIA.findall(xml))):
        digest = hashlib.sha256(archive.read(f"ppt/media/{target}")).hexdigest()
        xml += f"<!-- {target} sha256 {digest} -->"
    return xml.encode("utf-8")


def _keep(path: Path, xml: bytes) -> Path:
    # pptx の XML は 1 行に全部入っている。要素ごとに折ると、違いが「どの図形か」で読める
    path.write_text(xml.decode("utf-8").replace("><", ">\n<").replace("--><!--", "-->\n<!--") + "\n",
                    encoding="utf-8")
    return path


def differences(kept: Path, baked: Path) -> list[str]:
    """What separates two snapshots: a line per file that changed, went missing, or is new."""
    def files(root: Path) -> set[str]:
        return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}

    old, new = files(kept) if kept.is_dir() else set(), files(baked)
    found = [f"missing  {name}  (= kept, but the corpus no longer bakes it)" for name in sorted(old - new)]
    found += [f"new      {name}  (= baked, but not kept yet)" for name in sorted(new - old)]
    for name in sorted(old & new):
        if filecmp.cmp(kept / name, baked / name, shallow=False):
            continue
        before = (kept / name).read_text(encoding="utf-8").splitlines()
        after = (baked / name).read_text(encoding="utf-8").splitlines()
        line = next((index for index, (a, b) in enumerate(zip(before, after)) if a != b),
                    min(len(before), len(after)))
        was = before[line][:SHOWN] if line < len(before) else "(the file ends here)"
        now = after[line][:SHOWN] if line < len(after) else "(the file ends here)"
        found.append(f"changed  {name}  line {line + 1}\n    - {was}\n    + {now}")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="compare with the kept snapshot instead of rewriting it")
    parser.add_argument("--corpus", type=Path, default=CORPUS, help="the corpus to bake")
    parser.add_argument("--kept", type=Path, default=None,
                        help="where the snapshot is kept (default: <corpus>/snapshot)")
    args = parser.parse_args(argv)
    kept = args.kept or args.corpus / "snapshot"

    started = time.monotonic()
    with tempfile.TemporaryDirectory() as scratch:
        baked = Path(scratch) / "snapshot"
        try:
            written = bake(args.corpus, baked)
        except SnapshotError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        took = f"{time.monotonic() - started:.1f}s"
        if args.check:
            found = differences(kept, baked)
            for line in found:
                print(line)
            print(f"snapshot: {len(written)} files baked, {len(found)} differ from {kept} ({took})")
            return 1 if found else 0
        if kept.exists():
            shutil.rmtree(kept)
        shutil.copytree(baked, kept)
    size = sum(path.stat().st_size for path in kept.rglob("*") if path.is_file())
    print(f"snapshot: kept {len(written)} files ({size} bytes) at {kept} ({took})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
