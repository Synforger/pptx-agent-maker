"""How a message names a page: its place in the file, and the number printed on it when that differs.

検査の報告・`review` の差分・`titles` など、頁を指す出力が使う判定 (= 読み書きはしない)。刷られる番号の元になる
開始の番号は、焼いた file から `slide.first_slide_number` が読む。
"""

from __future__ import annotations


def page_number(page: int, first_number: int = 1) -> str:
    """A page as a report line names it: its place in the file, and the number printed on it when that differs.

    ⚠ **人は刷られた番号で頁を言う。**資料が開始を 0 にして表紙に番号を付けない時、表紙の次 (= ファイルの 2 番目)
    の頁に刷られるのは 1 で、プレビューも PowerPoint もそう見せる。位置だけを出すと、操作者の「2 ページ」を
    別の頁と取り違える。開始が 1 の資料は位置と刷られる番号が同じなので、そのまま出す。頁 0 は資料全体。
    """
    if first_number == 1 or page < 1:
        return str(page)
    return f"{page} (printed {first_number + page - 1})"


def page_label(page: int, first_number: int = 1) -> str:
    """`page_number` with the word in front (= "page 3 (printed 2)")."""
    return f"page {page_number(page, first_number)}"


def manifest_page_label(index: int) -> str:
    """A page as the manifest counts it (= the `index`th `[[pages]]`), for a message raised before any deck exists.

    ⚠ **組んでいる途中の失敗は、刷られる番号をまだ言えない。**数え始めは、全部の頁を置いてから決まる
    (= 表紙の次から数える資料は 0)。画面の頁と取り違えないよう、manifest の何番目かだと言い切る。
    """
    return f"page {index} of the manifest"
