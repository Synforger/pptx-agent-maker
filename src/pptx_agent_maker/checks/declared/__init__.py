"""Checks that read the manifest, not the built deck. Each has a NAME and a run(manifest, theme, config).

焼いた deck からは分からない事が在る ― どの頁が宣言で組まれたか、どの文字の枠が題か、その頁が
出所を書いたか。宣言を読めば全部書いてある。頁の番号は manifest の並びの番号で、焼いた deck の頁の
番号と同じ (= 1 つの宣言が 1 頁)。

頁が何を持つか (= 字の量・箱・主役) は宣言からは数えられず、型が組んだ頁の物 (= `Page.elements`) を読む。
そういう検査は `READS_PAGES = True` を持ち、`run` の第 4 引数に、manifest の番号 → 組んだ頁 の表を受け取る。
"""

from . import (crowded_page, long_title, no_lead, one_line_boxes, section_agenda, unnamed_axis, unsourced,
               untoned_cards, wordy_page)

ALL = (long_title, unsourced, unnamed_axis, section_agenda, untoned_cards,
       wordy_page, one_line_boxes, crowded_page, no_lead)

__all__ = ["ALL", "crowded_page", "long_title", "no_lead", "one_line_boxes", "section_agenda", "unnamed_axis",
           "unsourced", "untoned_cards", "wordy_page"]
