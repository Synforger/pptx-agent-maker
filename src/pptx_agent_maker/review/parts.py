"""Every difference between two decks, part by part.

読み取る項目を 1 つずつ足していく形は、足していない項目を黙って落とす。**先に全部
出す。**読みやすくするのはその後で、落とさないことが先。

.pptx は zip なので、比べる単位は中の部品 (= 頁 1 枚 / 画像 1 枚 / 頁の並び) そのものに
なる。文言も、画像の寸法も、トリミングも、色も、表の列幅も、全部この層を通る。

⚠ **除外は 2 つだけ。**同じデッキの手編集前後の 2 版を部品ごとに比べて測った。
そのうち中身に関係なく毎回動くのは `docProps/` (= 編集時刻と統計) と
`ppt/viewProps.xml` (= 最後に見ていた頁と表示倍率) の 3 部品だけだった。それ以外は
全部本物の変更なので落とさない。

⚠ **除外は前方一致で書く。**「この file 名だけ」と書いた除外は、次に増えた 1 本を
落とすか、逆に拾い損ねる。
"""

from __future__ import annotations

import difflib
import hashlib
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

# 中身と無関係に毎回動く部品 (= 実測で 3 本)。前方一致。
NOISE = ("docProps/", "ppt/viewProps.xml")
# text として差分を出す部品 (= それ以外は中身を見ずに大きさと hash で報告する)
TEXTUAL = re.compile(r"\.(xml|rels)$")
# PowerPoint が保存のたびに書き換える、中身と無関係な印。
# ⚠ **畳むだけで、隠さない。**畳んだ行数は必ず数えて出す (= 実測では全差分の
# 半分を超えた。残さないと本物の変更が埋もれる)。
CHURN = (
    (re.compile(r'\s*dirty="0"'), ""),          # スペルチェックの印
    (re.compile(r'\bid="\d+"'), 'id="#"'),       # 図形 id の振り直し
    (re.compile(r'name="([^"\d]+)\d+"'), r'name="\1#"'),  # id を埋めた既定名
)


def _canonical(line: str) -> str:
    """The line with PowerPoint's own churn removed, for matching only."""
    for pattern, replacement in CHURN:
        line = pattern.sub(replacement, line)
    return line


def _changes_in(diff: str) -> int:
    """How many + / - lines a diff actually prints."""
    return sum(1 for line in diff.splitlines()
               if line[:1] in "+-" and not line.startswith(("+++", "---")))


def _is_noise(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in NOISE)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def _lines(data: bytes) -> list[str]:
    """XML をタグ境界で改行しただけの形。

    整形して属性を並べ替えたりはしない ― 並べ替えると「本当に変わった所」と
    「並べ方が違うだけの所」の区別が消える。
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []
    return re.sub(r"><", ">\n<", text).splitlines()


@dataclass(frozen=True)
class Part:
    """One part of the package, and what happened to it."""

    name: str
    status: str  # "added" | "removed" | "changed"
    before: bytes | None
    after: bytes | None

    @property
    def textual(self) -> bool:
        return bool(TEXTUAL.search(self.name))

    def headline(self) -> str:
        if self.status == "added":
            return f"+ {self.name}  ({len(self.after or b''):,} bytes, {_digest(self.after or b'')})"
        if self.status == "removed":
            return f"- {self.name}  ({len(self.before or b''):,} bytes, {_digest(self.before or b'')})"
        return (f"~ {self.name}  ({len(self.before or b''):,} -> {len(self.after or b''):,} bytes, "
                f"{_digest(self.before or b'')} -> {_digest(self.after or b'')})")

    def diff(self, context: int = 0, fold_churn: bool = True) -> tuple[str, int]:
        """The unified diff for a textual part, and how many churn lines were folded.

        照合は churn を落とした形で取り、**出す行は実物のまま**にする (= 畳んだ形を
        表示すると、file に無い行を読ませることになる)。
        """
        if not self.textual or self.status != "changed":
            return "", 0
        before, after = _lines(self.before or b""), _lines(self.after or b"")
        if not before and not after:
            return "", 0
        if not fold_churn:
            return "\n".join(difflib.unified_diff(
                before, after, fromfile=f"a/{self.name}", tofile=f"b/{self.name}",
                lineterm="", n=context)), 0

        left, right = [_canonical(x) for x in before], [_canonical(x) for x in after]
        matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
        out: list[str] = [f"a/{self.name} -> b/{self.name}"]
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            out.append(f"@@ -{i1 + 1},{i2 - i1} +{j1 + 1},{j2 - j1} @@")
            out.extend(f"-{line}" for line in before[i1:i2])
            out.extend(f"+{line}" for line in after[j1:j2])

        # ⚠ **畳んだ量は「出さなかった行の実数」で言う。**照合の内訳から数えると、
        # 畳んだことで塊ごと消えた分が落ちて、実際より小さい数を報告する。
        raw, _ = self.diff(context=context, fold_churn=False)
        folded = max(0, _changes_in(raw) - _changes_in("\n".join(out)))
        if len(out) == 1:
            return "", folded
        return "\n".join(out), folded


@dataclass(frozen=True)
class Inventory:
    """What the whole comparison found."""

    total_before: int
    total_after: int
    identical: int
    parts: tuple[Part, ...]
    ignored: tuple[str, ...]

    @property
    def changed(self) -> int:
        return len(self.parts)

    def summary(self) -> str:
        return (f"parts {self.total_before} -> {self.total_after}: "
                f"{self.identical} identical, {self.changed} differ"
                + (f", {len(self.ignored)} ignored as noise" if self.ignored else ""))


def compare(built: Path, edited: Path) -> Inventory:
    """Open both packages and report every part that is not byte-identical."""
    with zipfile.ZipFile(Path(built)) as left, zipfile.ZipFile(Path(edited)) as right:
        names_left = {i.filename for i in left.infolist() if not i.is_dir()}
        names_right = {i.filename for i in right.infolist() if not i.is_dir()}
        ignored = sorted(n for n in names_left | names_right if _is_noise(n))
        names_left -= set(ignored)
        names_right -= set(ignored)

        found: list[Part] = []
        identical = 0
        for name in sorted(names_left | names_right):
            in_left, in_right = name in names_left, name in names_right
            before = left.read(name) if in_left else None
            after = right.read(name) if in_right else None
            if in_left and in_right:
                if before == after:
                    identical += 1
                    continue
                found.append(Part(name, "changed", before, after))
            elif in_right:
                found.append(Part(name, "added", None, after))
            else:
                found.append(Part(name, "removed", before, None))

    return Inventory(len(names_left), len(names_right), identical,
                     tuple(found), tuple(ignored))


def render(inventory: Inventory, *, full: bool = False, context: int = 0,
           fold_churn: bool = True) -> str:
    """The inventory as text: one line per part, and the diffs when asked."""
    out = [inventory.summary(), ""]
    folded = 0
    for part in inventory.parts:
        out.append(part.headline())
        if full:
            body, count = part.diff(context=context, fold_churn=fold_churn)
            folded += count
            if body:
                out.extend(["", body, ""])
    if not inventory.parts:
        out.append("(every part is byte-identical)")
    if full and folded:
        out.append(f"({folded} lines folded as PowerPoint's own churn — "
                   f"re-run with --raw to see them)")
    return "\n".join(out)
