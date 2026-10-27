"""What a check reports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """One problem on one page of a built deck.

    `page` is the page's place in the file (= 1 for the first; 0 is the whole deck), not the number printed on it.
    """

    check: str
    page: int
    what: str
    why: str

    def render(self, first_number: int = 1) -> str:
        return f"{page_label(self.page, first_number)}: {self.what}  <- {self.why}"


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


class Findings(list):
    """The findings of a run, and what the project let through by name (= `allowed`, one line each).

    ⚠ **通した物は当たりではないが、黙って通さない。**案件が「この組は通す」と書いた物 (= テンプレートの
    差し色の字) は数えず、終わり方も変えない。ただし報告には 1 行ずつ出す ― 出さないと、通した組が
    どこに何か所在るかも、その組がもう使われていないことも、誰にも見えない。
    """

    def __init__(self, found=(), allowed=()) -> None:
        super().__init__(found)
        self.allowed: list[str] = list(allowed)
