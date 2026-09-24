#!/usr/bin/env python3
"""Stop a push that carries words or values from private decks.

The anonymity guard compares what is sent with a list of names. A value copied
from a real deck while trying the toolkit out -- a measurement in a test table,
a page number in an example -- is on no list, so it goes through. This check
compares what is about to be pushed with the text of the private decks
themselves.

The decks are named on this machine only, never in the repository:

    ~/.config/private-corpus/sources.txt   one .pptx (or folder of them) per line
    ~/.config/private-corpus/words.txt     extra words, one per line (optional)
    ~/.config/private-corpus/allow.txt     phrases that are fine (optional)

A hit is any added line or commit message that holds
  - a run of text of 8 characters or more from one of the decks,
  - a number with three or more decimals that appears in them, or
  - a word from words.txt.

With no sources.txt the check says so and passes (CI has no private decks).

    private-corpus-check.py --range <from>..<to>
    private-corpus-check.py --commits <sha>...     (what a push is about to send)
    private-corpus-check.py --text <file>          (check one file's lines)
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

CONFIG = Path(os.environ.get("PRIVATE_CORPUS_DIR", Path.home() / ".config" / "private-corpus"))
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "private-corpus"
RUN = re.compile(r"<a:t\b[^>]*>(.*?)</a:t>", re.S)
NUMBER = re.compile(r"(?<![\d.])\d+\.\d{3,}(?![\d.])")
MIN_RUN = 8


def _lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def _decks() -> list[Path]:
    found = []
    for entry in _lines(CONFIG / "sources.txt"):
        path = Path(entry).expanduser()
        found.extend(sorted(path.rglob("*.pptx")) if path.is_dir() else [path])
    return [p for p in found if p.is_file() and not p.name.startswith("~$")]


def corpus() -> tuple[set[str], set[str], set[str]]:
    """Runs, numbers and words from the private sources (cached by the decks' size and time)."""
    decks = _decks()
    stamp = hashlib.sha256(json.dumps(
        [(str(d), d.stat().st_size, d.stat().st_mtime_ns) for d in decks]).encode()).hexdigest()
    cached = CACHE / f"{stamp}.json"
    if cached.is_file():
        data = json.loads(cached.read_text(encoding="utf-8"))
        runs, numbers = set(data["runs"]), set(data["numbers"])
    else:
        runs, numbers = set(), set()
        for deck in decks:
            with zipfile.ZipFile(deck) as archive:
                for name in archive.namelist():
                    if name.startswith("ppt/") and name.endswith(".xml"):
                        for text in RUN.findall(archive.read(name).decode("utf-8", "replace")):
                            text = html.unescape(text).strip()
                            if len(text) >= MIN_RUN:
                                runs.add(text)
                            numbers.update(NUMBER.findall(text))
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({"runs": sorted(runs), "numbers": sorted(numbers)},
                                     ensure_ascii=False), encoding="utf-8")
    allowed = set(_lines(CONFIG / "allow.txt"))
    return runs - allowed, numbers - allowed, set(_lines(CONFIG / "words.txt")) - allowed


def hits(lines: list[tuple[str, str]], runs, numbers, words) -> list[str]:
    found = []
    for where, line in lines:
        what = [w for w in words if w in line]
        what += [n for n in NUMBER.findall(line) if n in numbers]
        what += [r for r in runs if r in line]
        if what:
            found.append(f"{where}: {what[0]!r} in {line.strip()[:100]!r}")
    return found


def _outgoing(commits: list[str]) -> list[tuple[str, str]]:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              errors="replace", check=True).stdout
    lines = []
    for sha in commits:
        for line in git("log", "-1", "--format=%B", sha).splitlines():
            lines.append((f"{sha[:7]} message", line))
        current = "?"
        for line in git("show", "--format=", "-p", "--no-color", sha).splitlines():
            if line.startswith("+++ b/"):
                current = line[6:]
            elif line.startswith("+") and not line.startswith("+++"):
                lines.append((f"{sha[:7]} {current}", line[1:]))
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--range", dest="span")
    parser.add_argument("--commits", nargs="*")
    parser.add_argument("--text", type=Path)
    args = parser.parse_args(argv)
    if not (CONFIG / "sources.txt").is_file():
        print(f"private-corpus: NOT CHECKED — no {CONFIG / 'sources.txt'} on this machine")
        return 0
    runs, numbers, words = corpus()
    if args.text:
        lines = [(f"{args.text}:{n}", line) for n, line in
                 enumerate(args.text.read_text(encoding="utf-8").splitlines(), start=1)]
    elif args.commits is not None:
        lines = _outgoing(args.commits)
    elif args.span:
        lines = _outgoing(subprocess.run(["git", "rev-list", args.span], capture_output=True,
                                         text=True, check=True).stdout.split())
    else:
        parser.error("give --range, --commits or --text")
    found = hits(lines, runs, numbers, words)
    if found:
        print("private-corpus: these lines carry text or values from the private decks:")
        for line in found:
            print(f"  {line}")
        print("Replace them with made-up ones (or add a phrase that is fine to allow.txt).")
        return 1
    print(f"private-corpus: clean ({len(lines)} lines against {len(runs)} runs, "
          f"{len(numbers)} numbers, {len(words)} words)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
