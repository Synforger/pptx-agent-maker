"""Compare the pages of two versions of a deck.

    page_difference.py   1 頁の比べた結果 (= 違う画素の数、または片方に頁が無い)
    pictures.py          2 つの資料の頁の絵を重ねて、違う画素を数える (= 判定)
    report.py            結果を 1 頁 1 行と「変わった頁 N / 全 M」にする。書体が無い時の 1 行も (= 判定)
    bake.py              資料を頁ごとの絵に描く (= プレビューと同じ LibreOffice と pdftoppm)
    decks.py             2 つの資料を描いて比べる
    fonts.py             資料が名指した書体と、この機械に無い書体 (= 読み書き。`fc-match` を呼ぶ)
    font_match.py        `fc-match` の答えから、書体が入っているかを決める (= 判定)

⚠ 描くのに LibreOffice (`soffice`) と poppler (`pdftoppm`) が要る。プレビューが見つけるのと同じ所から見つける。
"""

from __future__ import annotations

from .decks import compare_decks
from .fonts import fonts_named, missing_fonts
from .page_difference import PageDifference
from .pictures import compare_pictures, count_differing_pixels
from .report import changed_count, render_font_note, render_report

__all__ = ["PageDifference", "compare_decks", "compare_pictures", "count_differing_pixels",
           "changed_count", "render_report", "render_font_note", "fonts_named", "missing_fonts"]
