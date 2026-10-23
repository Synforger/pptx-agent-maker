"""A card with no `tone`, in a project that names its own grounds.

案件が `[theme.grounds]` で地に名前 (= 意味) を付けている資料では、カードの地の色が意味を運ぶ。`tone` を書き
忘れたカードは道具の既定の薄い地 (= `box`) になり、案件が名付けた地のどれかと見分けがつかないことがある
(= 既定の薄い橙が、案件の橙の地と同じに見えた)。名前を宣言していない案件では、地は意味を運ばないので見ない。

見るのは宣言で組む頁のカード (= `cards` の並びと、`compose` のマスや入れ物の中の `card`)。`["見出し", "本文"]`
の書き方は `tone` を持てないので、名前を宣言した案件では当たる (= 表の書き方にして `tone` を書く)。
"""

from __future__ import annotations

from ..finding import Finding

NAME = "untoned_cards"


def _untoned(written) -> int:
    """How many cards under `written` say no `tone`."""
    count = 0
    if isinstance(written, dict):
        for key, value in written.items():
            if key == "cards" and isinstance(value, list):
                count += sum(1 for card in value if not (isinstance(card, dict) and "tone" in card))
                count += sum(_untoned(card) for card in value)
            elif key == "card":
                count += 0 if isinstance(value, dict) and "tone" in value else 1
                count += _untoned(value)
            else:
                count += _untoned(value)
    elif isinstance(written, list):
        count += sum(_untoned(value) for value in written)
    return count


def run(manifest, theme=None, config: dict | None = None) -> list[Finding]:
    """A project may switch the check off (= `[checks] untoned_cards = false`)."""
    if (config or {}).get(NAME, True) is False or theme is None or not theme.ground_names():
        return []
    findings: list[Finding] = []
    for number, entry in enumerate(manifest.entries, start=1):
        if entry.kind != "declare":
            continue
        count = _untoned(entry.data)
        if count:
            findings.append(Finding(
                NAME, number, str(entry.data.get("title", ""))[:60],
                f"{count} card{'s' if count > 1 else ''} with no `tone` — in a project that names its grounds "
                "(`[theme.grounds]`), a card without one takes the plain ground `box`; write the tone it means"))
    return findings
