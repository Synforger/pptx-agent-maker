#!/usr/bin/env python3
"""Measure how far each character moves the line along, and print the tables tokens.py keeps.

    uv run python scripts/generate/measure-advance.py GROUP=regular.ttf,bold.ttf[+regular.ttf,bold.ttf] ...

A group is one row of `_ADVANCE` (= the regular faces) and of `_ADVANCE_BOLD` (= the bold ones) in
`src/pptx_agent_maker/layout/tokens.py`: the typefaces that share one table (`+` joins several, and the
table takes the widest of them per character). The
group named `any` is the one a typeface nobody measured falls back to, so give it the widest
faces a deck is likely to use. It also prints `_SQUARE`: the symbols (= ■ ● → ※ — … ①) that any of its
faces sets a full square wide, which `advance` counts as one square in every typeface but the monospaced one.

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
import unicodedata

from PIL import Image, ImageDraw, ImageFont

CHARACTERS = string.ascii_letters + string.digits + " " + string.punctuation
SIZE = 1000
STEP = 20  # thousandths of the type size
#: Symbols below the full-width range (= `advance` counts everything from U+2E80 as one square already).
SYMBOLS = range(0xA0, 0x2E80)
#: A symbol this wide in any face counts as a full square: the Japanese faces draw their symbols one em wide.
SQUARE = 0.98
#: Characters that stand on the one before them or break the line: no width of their own to count.
NOT_COUNTED = frozenset({"Mn", "Mc", "Me", "Cc", "Cf", "Zl", "Zp"})
PROBE_SIZE = 60
RUNS_A_LINE = 4


def widths(path: str) -> dict[str, float]:
    font = ImageFont.truetype(path, SIZE)
    return {character: font.getlength(character) / SIZE for character in CHARACTERS}


def squares(paths: list[str]) -> list[tuple[int, int]]:
    """Runs of code points that any of these faces holds and sets a full square wide.

    A face is asked for a character it does not hold with the glyph it draws for "nothing" (= `.notdef`), so a
    character counts as held when it is drawn differently from U+FFFF.
    """
    wide = set()
    for path in paths:
        measuring = ImageFont.truetype(path, SIZE, layout_engine=ImageFont.Layout.BASIC)
        probing = ImageFont.truetype(path, PROBE_SIZE, layout_engine=ImageFont.Layout.BASIC)
        nothing = _drawn(probing, "\uffff")
        wide |= {code for code in SYMBOLS
                 if unicodedata.category(chr(code)) not in NOT_COUNTED and _drawn(probing, chr(code)) != nothing
                 and measuring.getlength(chr(code)) / SIZE >= SQUARE}
    runs: list[tuple[int, int]] = []
    for code in sorted(wide):
        if runs and runs[-1][1] + 1 == code:
            runs[-1] = (runs[-1][0], code)
        else:
            runs.append((code, code))
    return runs


def _drawn(font: ImageFont.FreeTypeFont, character: str) -> bytes:
    image = Image.new("L", (PROBE_SIZE * 3, PROBE_SIZE * 3))
    ImageDraw.Draw(image).text((PROBE_SIZE // 3, PROBE_SIZE // 3), character, font=font, fill=255)
    return image.tobytes()


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
    regular_rows, bold_rows, ratios, square_rows = [], [], [], []
    for argument in arguments:
        group, _equals, faces = argument.partition("=")
        regular, bold, paths = [], [], []
        for face in faces.split("+"):
            plain, _comma, heavy = face.partition(",")
            regular.append(widths(plain))
            bold.append(widths(heavy) if heavy else regular[-1])
            paths += [plain, heavy] if heavy else [plain]
        if group == "any":
            runs = [f"(0x{first:04X}, 0x{last:04X})," for first, last in squares(paths)]
            square_rows = [f"    {' '.join(runs[at:at + RUNS_A_LINE])}" for at in range(0, len(runs), RUNS_A_LINE)]
        regular_rows += table(group, regular)
        bold_rows += table(group, bold)
        widest = max(sum(heavy[c] for c in string.ascii_lowercase) / sum(plain[c] for c in string.ascii_lowercase)
                     for plain, heavy in zip(regular, bold))
        ratios.append(f"    # bold, {group}: {widest:.3f}")
    print("\n".join(["# _ADVANCE", *regular_rows, "# _ADVANCE_BOLD", *bold_rows, *ratios, "# _SQUARE", *square_rows]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
