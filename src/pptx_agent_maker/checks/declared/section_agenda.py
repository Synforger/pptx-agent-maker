"""A long chapter of several parts that does not come back to its agenda at the head of each part.

章の頁が増えると、読み手は今どこに居て、章が全体でどうまとまっているかを見失う。章の頭の目次 1 枚では、
3 つ目の段に入った頃には最初の目次が遠い。章の頁 (= 目次を除く) が `LONG` を超え、中の段 (= 目次の小項目) が
2 つ以上ある章は、中の段の頭ごとに目次を挟む (= 同じ章を `highlight` し、その段を `highlight_item` で強調した
`look = "cards"` の目次)。

章の範囲は manifest の並びで決める ― 章を `highlight` した目次から、別の章を名指す目次 (か、章を名指さない
目次) の手前まで。章の中の段は、その章の目次の `buckets` が書いた小項目。読むのは宣言で組む目次だけ
(= 複製や輸入の目次は、どの章を強調したかが宣言から読めない)。

`LONG` は、目次 1 枚から次の目次までの間を、人が「今どこか」を覚えていられる長さとして置いた値で、実測では
ない。案件が `[checks] section_agenda = <頁の数>` で変えられ、`false` で外せる。
"""

from __future__ import annotations

from ..finding import Finding

NAME = "section_agenda"

#: 中の段ごとの目次が要る章の長さ (= 目次を除く頁の数が、これを超えたら)
LONG = 6


def _long(config: dict | None) -> int | None:
    """How many pages a chapter may run to with one agenda (= None when the project switched the check off)."""
    said = (config or {}).get(NAME, True)
    if said is False:
        return None
    if said is True:
        return LONG
    if isinstance(said, bool) or not isinstance(said, int) or said < 1:
        raise ValueError(f"[checks] {NAME} is {said!r} — the number of pages a chapter runs to before each of its "
                         "parts needs an agenda of its own (= 6), or false")
    return said


def _chapters(manifest) -> list[dict]:
    """Each chapter as the manifest runs: where its agenda is, its parts, the parts an agenda marks, its pages."""
    chapters: list[dict] = []
    current: dict | None = None
    for number, entry in enumerate(manifest.entries, start=1):
        data = entry.data if entry.kind == "declare" else {}
        if data.get("type") == "agenda":
            here = data.get("highlight")
            if not isinstance(here, int) or isinstance(here, bool) or here < 1:
                current = None
                continue
            if current is None or current["chapter"] != here:
                buckets = data.get("buckets") or []
                # 章の名前と小項目 (= 型が `[名前, [小項目, …]]` を確かめる。形の崩れた目次は型が止めるので、ここは数えない)
                title, items = (buckets[here - 1][0], buckets[here - 1][1]) if here <= len(buckets) else ("", [])
                current = {"chapter": here, "page": number, "title": str(title), "parts": len(items),
                           "marked": set(), "pages": 0}
                chapters.append(current)
            item = data.get("highlight_item")
            if isinstance(item, int) and not isinstance(item, bool):
                current["marked"].add(item)
            continue
        if current is not None:
            current["pages"] += 1
    return chapters


def run(manifest, theme=None, config: dict | None = None) -> list[Finding]:
    long = _long(config)
    if long is None:
        return []
    findings: list[Finding] = []
    for chapter in _chapters(manifest):
        if chapter["parts"] < 2 or chapter["pages"] <= long:
            continue
        missing = [part for part in range(1, chapter["parts"] + 1) if part not in chapter["marked"]]
        if missing:
            findings.append(Finding(
                NAME, chapter["page"], chapter["title"][:60],
                f"chapter {chapter['chapter']} runs to {chapter['pages']} pages over {chapter['parts']} parts — put an "
                f"agenda at the head of each part (look = \"cards\", highlight_item = "
                f"{', '.join(str(part) for part in missing)} not yet)"))
    return findings
