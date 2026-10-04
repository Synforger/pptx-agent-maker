#!/usr/bin/env python3
"""Measure how far each character moves the line along, and print the table tokens.py keeps.

    .venv/bin/python scripts/generate/measure-advance.py GROUP=regular.ttf,bold.ttf[+regular.ttf,bold.ttf] ...

A group is one row of `_ADVANCE` in `src/pptx_agent_maker/layout/base/tokens.py`: the typefaces that
share one table (`+` joins several, and the table takes the widest of them per character). The
group named `any` is the one a typeface nobody measured falls back to, so give it the widest
faces a deck is likely to use.

    .venv/bin/python scripts/generate/measure-advance.py \\
        any=Verdana.ttf,"Verdana Bold.ttf"+meiryo.ttc,meiryob.ttc \\
        arial=Arial.ttf,"Arial Bold.ttf"

Widths are fractions of the type size, read from the font file itself and rounded **up** to
0.02: an estimate that runs narrow lets a heading spill onto the line below it. The bold figure
is how much wider the lowercase runs in bold, for the widest face of the group.
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


def main(arguments: list[str]) -> int:
    if not arguments:
        print(__doc__)
        return 2
    for argument in arguments:
        group, _equals, faces = argument.partition("=")
        regular, bold = [], []
        for face in faces.split("+"):
            plain, _comma, heavy = face.partition(",")
            regular.append(widths(plain))
            bold.append(widths(heavy) if heavy else None)
        widest = {c: max(table[c] for table in regular) for c in CHARACTERS}
        steps: dict[float, list[str]] = {}
        for character, wide in widest.items():
            rounded = -(-round(wide * 1000) // STEP) * STEP / 1000
            steps.setdefault(rounded, []).append(character)
        print(f'    "{group}": {{')
        for step in sorted(steps):
            print(f"        {step:.2f}: {''.join(sorted(steps[step]))!r},")
        print("    },")
        ratios = [sum(heavy[c] for c in string.ascii_lowercase) / sum(plain[c] for c in string.ascii_lowercase)
                  for plain, heavy in zip(regular, bold) if heavy]
        if ratios:
            print(f"    # bold, {group}: {max(ratios):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
