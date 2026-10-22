"""What a check reports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """One problem on one page of a built deck."""

    check: str
    page: int
    what: str
    why: str

    def render(self) -> str:
        return f"page {self.page}: {self.what}  <- {self.why}"


class Findings(list):
    """The findings of a run, and what the project let through by name (= `allowed`, one line each).

    ⚠ **通した物は当たりではないが、黙って通さない。**案件が「この組は通す」と書いた物 (= テンプレートの
    差し色の字) は数えず、終わり方も変えない。ただし報告には 1 行ずつ出す ― 出さないと、通した組が
    どこに何か所在るかも、その組がもう使われていないことも、誰にも見えない。
    """

    def __init__(self, found=(), allowed=()) -> None:
        super().__init__(found)
        self.allowed: list[str] = list(allowed)
