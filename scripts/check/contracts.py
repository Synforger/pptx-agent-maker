"""Check the table of promises (`tests/contracts.txt`) against the tests and the code that are really there.

`task ci` runs it. It reports, one line each, a test file that no row names, a row whose test file or target is
missing, and a row with no promise, and ends with 1 when it reported anything:

    contracts.py              check this repository
    contracts.py --root DIR   check the repository at DIR (= the tests of this script)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TABLE = Path("tests/contracts.txt")
TEST_GLOBS = ("tests/**/test_*.py", "preview/tests/test_*.py")
FIELD_COUNT = 3


def rows(table: Path) -> list[tuple[int, list[str]]]:
    """The rows of the table with their line numbers; comments and blank lines are left out."""
    found = []
    for number, line in enumerate(table.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip() and not line.lstrip().startswith("#"):
            found.append((number, [field.strip() for field in line.split("|")]))
    return found


def problems(root: Path) -> list[str]:
    """Every way the table and the repository disagree, as lines to print."""
    table = root / TABLE
    if not table.is_file():
        return [f"{TABLE}: no table of promises"]
    found = []
    named = set()
    for number, fields in rows(table):
        where = f"{TABLE}:{number}"
        if len(fields) != FIELD_COUNT:
            found.append(f"{where}: a row has {FIELD_COUNT} fields (target | test | promise), this one has {len(fields)}")
            continue
        target, test, promise = fields
        named.add(test)
        if not (root / target).exists():
            found.append(f"{where}: the target {target} does not exist")
        if not (root / test).is_file():
            found.append(f"{where}: the test {test} does not exist")
        if not promise:
            found.append(f"{where}: the row for {test} says no promise")
    tests = sorted({path.relative_to(root).as_posix() for pattern in TEST_GLOBS for path in root.glob(pattern)})
    found.extend(f"{test}: no row of {TABLE} names this test" for test in tests if test not in named)
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    found = problems(parser.parse_args().root)
    for line in found:
        print(line)
    print(f"contracts: {len(found)} problem(s)")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
