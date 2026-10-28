"""Print what comparing two decks found: one line per page, then how many pages changed.

Takes the `PageDifference`s `pictures.py` made; touches no file.
"""

from __future__ import annotations

from .._common.page_label import page_label
from .page_difference import PageDifference


def changed_count(differences: list[PageDifference]) -> int:
    """How many pages changed (= a page one deck lacks counts)."""
    return sum(1 for difference in differences if difference.is_changed)


def render_report(differences: list[PageDifference], first_number: int = 1) -> str:
    """The report: a line for each page and, last, `changed N of M pages`.

    ⚠ **頁の数が違う時は、足りない側の頁を「無い」と書く。**数を並べる欄に 0 を入れると変わっていない頁に
    見える。``first_number`` は頁に刷られる番号の開始で、頁の呼び方は他の報告と同じ (= `page_label`)。
    """
    lines = [_line(difference, first_number) for difference in differences]
    lines.append(f"changed {changed_count(differences)} of {len(differences)} pages")
    return "\n".join(lines)


def render_font_note(missing: list[str] | None) -> str | None:
    """The one line that says why pages with words may differ when nothing changed, or None when there is nothing to say.

    ``missing`` は `fonts.missing_fonts` の答え: 資料が名指して、この機械に無い書体 (= 無ければ空、
    `fc-match` が無い機械では None)。数の報告は変えず、この行は別に出す (= 終わりの code も変えない)。
    """
    if missing is None:
        return "note: fc-match is not on this machine, so whether the typefaces the decks name are installed was not checked"
    if not missing:
        return None
    return (f"note: a deck names {', '.join(missing)}, which this machine does not have: LibreOffice draws its words "
            "in a stand-in face that can change from one run to the next, so pages with words may differ when "
            "nothing changed")


def _line(difference: PageDifference, first_number: int) -> str:
    label = page_label(difference.number, first_number)
    if difference.before_size is None:
        return f"{label}: not in the before deck"
    if difference.after_size is None:
        return f"{label}: not in the after deck"
    if not difference.is_comparable:
        before, after = (f"{width}x{height}" for width, height in (difference.before_size, difference.after_size))
        return f"{label}: drawn at another size (before {before}, after {after})"
    return f"{label}: {difference.differing_pixels} px differ ({difference.ratio:.4%})"
