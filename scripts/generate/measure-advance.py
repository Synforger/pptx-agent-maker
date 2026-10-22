#!/usr/bin/env python3
"""Measure how far each character moves the line along, and print the tables tokens.py keeps.

    uv run python scripts/generate/measure-advance.py GROUP=regular.ttf,bold.ttf[+regular.ttf,bold.ttf] ...

A group is one row of `_ADVANCE` (= the regular faces) and of `_ADVANCE_BOLD` (= the bold ones) in
`src/pptx_agent_maker/layout/tokens.py`: the typefaces that share one table (`+` joins several, and the
table takes the widest of them per character). The
group named `any` is the one a typeface nobody measured falls back to, so give it the widest
faces a deck is likely to use.

    uv run python scripts/generate/measure-advance.py \\
        any=Verdana.ttf,"Verdana Bold.ttf"+meiryo.ttc,meiryob.ttc \\
        arial=Arial.ttf,"Arial Bold.ttf"

Widths are fractions of the type size, read from the font file itself and rounded **up** to
0.02: an estimate that runs narrow lets a heading spill onto the line below it. The bold table is
measured character by character too (= a bold face widens its letters by different amounts, and some
not at all: Arial's figures), and the bold figure printed after it is how much wider the lowercase runs
in bold, for the widest face of the group (= what a character outside the tables is counted with).
"""

from __future__ import annotations

import string
import sys

from PIL import ImageFont

CHARACTERS = string.ascii_letters + string.digits + " " + string.punctuation
SIZE = 1000
STEP = 20  # thousandths of the type size


def widths(path: str) -> dict[str, float]:
    font = ImageFont.truetype(path, SIZE)
    return {character: font.getlength(character) / SIZE for character in CHARACTERS}


def table(group: str, faces: list[dict[str, float]]) -> list[str]:
    """One group's rows: each width, rounded up to the step, and the characters that take it."""
    widest = {c: max(face[c] for face in faces) for c in CHARACTERS}
    steps: dict[float, list[str]] = {}
    for character, wide in widest.items():
        rounded = -(-round(wide * 1000) // STEP) * STEP / 1000
        steps.setdefault(rounded, []).append(character)
    return ([f'    "{group}": {{']
            + [f"        {step:.2f}: {''.join(sorted(steps[step]))!r}," for step in sorted(steps)]
            + ["    },"])


def main(arguments: list[str]) -> int:
    if not arguments:
        print(__doc__)
        return 2
    regular_rows, bold_rows, ratios = [], [], []
    for argument in arguments:
        group, _equals, faces = argument.partition("=")
        regular, bold = [], []
        for face in faces.split("+"):
            plain, _comma, heavy = face.partition(",")
            regular.append(widths(plain))
            bold.append(widths(heavy) if heavy else regular[-1])
        regular_rows += table(group, regular)
        bold_rows += table(group, bold)
        widest = max(sum(heavy[c] for c in string.ascii_lowercase) / sum(plain[c] for c in string.ascii_lowercase)
                     for plain, heavy in zip(regular, bold))
        ratios.append(f"    # bold, {group}: {widest:.3f}")
    print("\n".join(["# _ADVANCE", *regular_rows, "# _ADVANCE_BOLD", *bold_rows, *ratios]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
