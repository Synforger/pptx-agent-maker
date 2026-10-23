"""Checks that read the manifest, not the built deck. Each has a NAME and a run(manifest, theme, config).

焼いた deck からは分からない事が在る ― どの頁が宣言で組まれたか、どの文字の枠が題か、その頁が
出所を書いたか。宣言を読めば全部書いてある。頁の番号は manifest の並びの番号で、焼いた deck の頁の
番号と同じ (= 1 つの宣言が 1 頁)。
"""

from . import long_title, section_agenda, unnamed_axis, unsourced, untoned_cards

ALL = (long_title, unsourced, unnamed_axis, section_agenda, untoned_cards)

__all__ = ["ALL", "long_title", "section_agenda", "unnamed_axis", "unsourced", "untoned_cards"]
