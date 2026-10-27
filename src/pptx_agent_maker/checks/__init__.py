"""Checking a deck after it is built.

    finding.py       当たりの形
    _internal/       描かれる物・色・絵の読み方 (= 焼いたものを読み直すのは根の `_common/slide.py`)
    rules/           焼いた deck を見る検査、1 検査 1 file
    declared/        manifest を見る検査、1 検査 1 file (= 焼いた file からは分からない事)

宣言層は置く前に解くので、ここが見るのは**宣言層を通っていない頁** ― テンプレートの複製と、
過去デッキからの輸入。どちらも座標は過去の誰かが手で置いたもので、誰も保証していない。

⚠ **これは焼いた後の検査であって、読みやすさの保証ではない。**座標が正しくても、
どれを見ればよいかは人が決める。焼いて目で見る工程は消えない。
"""

from __future__ import annotations

from pathlib import Path

from .finding import Finding, Findings, page_label, page_number
from .declared import ALL as DECLARED
from .rules import ALL as CHECKS

__all__ = ["Finding", "Findings", "page_label", "page_number", "CHECKS", "DECLARED",
           "run_all", "run_declared", "run_built", "report"]


def run_all(deck: Path | str, config: dict | None = None) -> list[Finding]:
    """Every check over one built deck."""
    deck = Path(deck)
    findings = Findings()
    for check in CHECKS:
        found = check.run(deck, config or {})
        findings.extend(found)
        findings.allowed.extend(getattr(found, "allowed", ()))
    return findings


def run_declared(manifest, theme, config: dict | None = None) -> list[Finding]:
    """Every check that reads the manifest (= what the built deck cannot say about itself)."""
    findings: list[Finding] = []
    for check in DECLARED:
        findings.extend(check.run(manifest, theme, config or {}))
    return findings


def run_built(deck: Path | str, manifest, theme, config: dict | None = None) -> list[Finding]:
    """Every check over a deck just built from its manifest: the built deck's, then the manifest's.

    ⚠ **同じ名前の検査が両側に在るものは、宣言の頁では宣言の側だけが言う** (= `long_title`)。宣言の頁の
    題はレイアウトの題の枠に書かれるので、焼いた deck の側からも題として見える。両側で数えると、同じ頁を
    2 度言うか、数え方の違いで食い違う ― 宣言の側は、頁が帯の高さを取ったのと同じ数を読む。
    """
    both = {check.NAME for check in CHECKS} & {check.NAME for check in DECLARED}
    declared = {number for number, entry in enumerate(manifest.entries, start=1) if entry.kind == "declare"}
    found = run_all(deck, config)
    built = [finding for finding in found if not (finding.check in both and finding.page in declared)]
    return Findings(built + run_declared(manifest, theme, config), found.allowed)


def report(findings: list[Finding], declared: bool = False, first_number: int = 1) -> str:
    """The findings, then a line per check so a clean deck still says what was looked at.

    `declared` は、manifest を見る検査も回したか (= `build` は回す。焼いた deck だけを渡された
    `check` は回せない)。回していない検査を「ok」と言わない。案件が通した物 (= `Findings.allowed`) は、
    その検査の行の下に `pass` で 1 行ずつ出す (= 数えないが、黙って通さない)。

    `first_number` は資料の最初の頁に刷られる番号 (= 1 でなければ、頁の位置に刷られる番号を並べる)。
    """
    lines = [finding.render(first_number) for finding in sorted(findings, key=lambda f: f.page)]
    if first_number != 1 and any(finding.page >= 1 for finding in findings):
        lines.append(f"  (this deck's first page prints {first_number}: \"page N\" counts from the first page of "
                     "the file, \"printed M\" is the number PowerPoint and the preview show)")
    lines.append("")
    names = list(dict.fromkeys(check.NAME for check in (*CHECKS, *(DECLARED if declared else ()))))
    for name in names:
        count = sum(1 for f in findings if f.check == name)
        lines.append(f"  {'FAIL' if count else 'ok':4}  {name:<16} {count}")
        lines.extend(f"  {'pass':4}  {name:<16} {what}" for check, what in getattr(findings, "allowed", ())
                     if check == name)
    return "\n".join(lines)
