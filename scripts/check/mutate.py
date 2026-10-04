"""Break the code the ways a table lists, and see that the tests go red each time.

test が緑でも、その test が見張っているつもりの物を本当に見ているかは分からない ― 実装を
わざと壊して赤になるのを見て、初めて「見張っている」と言える。壊し方を表 (= `tests/mutants/`)
に書いておけば、同じ確かめを次の人が 1 手で打てる。

    mutate.py tests/mutants/<topic>.toml

表の形:

    tests = ["tests/test_geometry.py"]        # 流す test (= 速い物に絞る)

    [[mutant]]
    name = "touching edges count as overlapping"
    file = "src/pptx_agent_maker/layout/geometry.py"
    old = "and other.left < self.right"        # この file にちょうど 1 か所だけ在る文字列
    new = "and other.left <= self.right"

⚠ **壊すたびに新しい写しで流す。**同じ場所で書き換えて戻す形は、大きさの変わらない書き換えが
同じ秒のうちに起きると、前の版の bytecode がそのまま読まれる (= 壊したのに緑)。

⚠ **赤の数は pytest の末尾の行から読む。**test の名前で拾うと、subTest の赤を取りこぼす。

⚠ **壊せなかった壊し方は、緑と同じく失敗に数える** (= 実装が動いて表が古くなった印。黙って
飛ばすと、表は減っていくのに「全部赤」と言い続ける)。道具は止めずに次の壊し方へ進む。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: git の外に在る木を写すときに入らない folder (= 作り物の木を渡す test のため)
NOT_SOURCE = frozenset({".git", ".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist",
                        "node_modules"})

_COUNT = re.compile(r"(\d+) (failed|errors?|passed)\b")


class TableError(ValueError):
    """The table of mutants cannot be read."""


@dataclass(frozen=True)
class Mutant:
    name: str
    file: str
    old: str
    new: str


@dataclass(frozen=True)
class Run:
    """What one run of the tests came to."""

    red: int        # 赤 (= failed と error の合計)
    passed: int
    said: str       # pytest の出力 (= 道具の側の失敗を見せるため)


def load(path: Path) -> tuple[list[str], list[Mutant]]:
    """The tests to run and the ways to break the code, from one table."""
    with Path(path).open("rb") as handle:
        table = tomllib.load(handle)
    unknown = sorted(set(table) - {"tests", "mutant"})
    if unknown:
        raise TableError(f"{path}: does not take {', '.join(unknown)} (= it takes tests, mutant)")
    tests = table.get("tests")
    if not isinstance(tests, list) or not tests:
        raise TableError(f"{path}: `tests` names the test files to run, at least one")
    mutants = []
    for number, entry in enumerate(table.get("mutant") or [], start=1):
        keys = {"name", "file", "old", "new"}
        if not isinstance(entry, dict) or set(entry) != keys:
            raise TableError(f"{path}: mutant {number} takes exactly {', '.join(sorted(keys))}")
        if entry["old"] == entry["new"]:
            raise TableError(f"{path}: mutant {number} ({entry['name']!r}) changes nothing")
        mutants.append(Mutant(*(str(entry[key]) for key in ("name", "file", "old", "new"))))
    if not mutants:
        raise TableError(f"{path}: no [[mutant]] — a table with nothing to break proves nothing")
    return [str(test) for test in tests], mutants


def _files(root: Path) -> list[Path]:
    """What a copy of the tree is made of: what git tracks or would track, else every source file."""
    listed = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard"],
                            capture_output=True, text=True)
    if listed.returncode == 0 and listed.stdout.strip():
        names = [Path(line) for line in listed.stdout.splitlines()]
    else:
        names = [path.relative_to(root) for path in root.rglob("*")
                 if not NOT_SOURCE & set(path.relative_to(root).parts)]
    return [name for name in names if (root / name).is_file()]


def _copy(root: Path, files: list[Path], to: Path) -> Path:
    for name in files:
        (to / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, to / name)
    return to


def _run(tree: Path, tests: list[str]) -> Run:
    """Run the tests inside a copy and count from pytest's last line."""
    done = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", *tests, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=tree, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    said = done.stdout + done.stderr
    last = next((line for line in reversed(done.stdout.splitlines()) if line.strip()), "")
    counts = {"failed": 0, "error": 0, "passed": 0}
    for number, what in _COUNT.findall(last):
        counts[what.rstrip("s") if what.startswith("error") else what] += int(number)
    # 終了コード 0 / 1 / 2 は「全部緑 / 赤が在る / 集める段で落ちた」。それ以外と、末尾に件数の
    # 無い出力は、test が走っていない (= 道具の側の失敗で、赤とも緑とも言えない)
    if done.returncode not in (0, 1, 2) or not _COUNT.search(last):
        raise RuntimeError(f"pytest did not run the tests (exit {done.returncode}):\n{said}")
    return Run(counts["failed"] + counts["error"], counts["passed"], said)


def _say(line: str) -> None:
    # pipe 越しでは溜め込まれて、終わるまで何も出ない (= 2 分黙る道具は、止まったのと見分けられない)
    print(line, flush=True)


def mutate(root: Path, tests: list[str], mutants: list[Mutant], say=_say) -> int:
    """Run the baseline, then each mutant in a copy of its own; how many did not go red."""
    files = _files(root)
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as scratch:
        baseline = _run(_copy(root, files, Path(scratch) / "baseline"), tests)
    if not baseline.passed:
        raise RuntimeError(f"the baseline has no passing test, so nothing can turn red:\n{baseline.said}")
    say(f"baseline: {baseline.red} red, {baseline.passed} passed "
        f"({time.monotonic() - started:.1f}s) — a mutant is red when it adds to that")

    survived = unbroken = 0
    for mutant in mutants:
        source = root / mutant.file
        found = source.read_text(encoding="utf-8").count(mutant.old) if source.is_file() else -1
        if found != 1:
            unbroken += 1
            why = "no such file" if found < 0 else f"`old` is there {found} times, not once"
            say(f"  ----   cannot break   {mutant.name}  <- {mutant.file}: {why}")
            continue
        with tempfile.TemporaryDirectory() as scratch:
            tree = _copy(root, files, Path(scratch) / "mutant")
            target = tree / mutant.file
            target.write_text(target.read_text(encoding="utf-8").replace(mutant.old, mutant.new),
                              encoding="utf-8")
            run = _run(tree, tests)
        if run.red > baseline.red:
            say(f"  red    {run.red - baseline.red:>3} more      {mutant.name}")
        else:
            survived += 1
            say(f"  GREEN  survived      {mutant.name}  <- no test noticed")
    red = len(mutants) - survived - unbroken
    say(f"mutants: {len(mutants)} — {red} red, {survived} survived, {unbroken} could not be applied "
        f"({time.monotonic() - started:.1f}s)")
    return survived + unbroken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("table", type=Path, help="a table of mutants, e.g. tests/mutants/look.toml")
    parser.add_argument("--root", type=Path, default=REPO, help="the tree to break (default: this repository)")
    args = parser.parse_args(argv)
    try:
        tests, mutants = load(args.table)
        left = mutate(args.root.resolve(), tests, mutants)
    except (TableError, OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
