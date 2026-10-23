"""The look of the name under a picture (= `[theme] caption_look`).

⚠ **絵が何かを示す名 (= どの手法の結果か、入力か正解か) を、出所と同じ灰の小さい字で置くと読み飛ばされる。**
案件はマスを入れ子にして太字の文章を絵の上に置いて代わりにしたが、段が絵より高いと名が絵から離れて段の底に
落ちた。`label` は絵のすぐ下の名を、本文の色の太字 (= `role = "label"` と同じ大きさ) にする。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.tokens import DEFAULT, ThemeError, theme_from  # noqa: E402

LABEL = theme_from({"caption_look": "label"})
LONG = "The output of the second model on the validation set, before the threshold was tuned for recall"


def build(spec, theme):
    return types.build({"title": "A page", **spec}, lambda name: Path(name), lambda path: 1.6, theme)


def caption(built):
    return next(e for e in built.build() if e.kind == "caption")


def picture(built):
    return next(e for e in built.build() if e.kind == "figure")


class TheNameUnderAPicture(unittest.TestCase):
    def test_left_unsaid_it_is_small_and_grey_as_before(self) -> None:
        name = caption(build({"type": "figure", "figure": "x.png", "caption": "Model A"}, DEFAULT))
        self.assertEqual((DEFAULT.type.caption, False, DEFAULT.palette.muted), (name.size, name.bold, name.colour))

    def test_as_a_label_it_is_bold_in_the_body_colour_at_the_size_of_a_label(self) -> None:
        name = caption(build({"type": "figure", "figure": "x.png", "caption": "Model A"}, LABEL))
        self.assertEqual((LABEL.type.stage, True, LABEL.palette.ink), (name.size, name.bold, name.colour))

    def test_it_stands_just_under_the_picture_in_every_place_a_picture_takes_a_name(self) -> None:
        pages = {
            "figure": {"type": "figure", "figure": "x.png", "caption": LONG},
            "figures": {"type": "figures", "figures": [["x.png", LONG], ["y.png", "Model B"]]},
            "compose": {"type": "compose", "rows": [{"cells": [{"figure": "x.png", "caption": LONG}, {"text": "t"}]}]},
        }
        for name, spec in pages.items():
            with self.subTest(name):
                built = build(spec, LABEL)
                shown, under = picture(built), caption(built)
                self.assertEqual(shown.rect.bottom + LABEL.spacing.gap_s, under.rect.top)
                self.assertEqual(LABEL.caption_height(under.text, under.rect.width), under.rect.height)

    def test_the_room_kept_for_the_name_is_counted_in_its_own_size_and_weight(self) -> None:
        """太字の大きい字は、同じ幅で灰の小さい字より多く折れる (= 取る高さもその行ぶん)。太さも数える ― 細字なら
        収まる幅で、太字は 1 行多く折れる。"""
        stage, inset = LABEL.type.stage, LABEL.spacing.text_inset
        width = DEFAULT.frame().width // 3
        self.assertGreater(LABEL.caption_height(LONG, width), DEFAULT.caption_height(LONG, width))
        # 細字と太字で折れる行が違う幅を探す (= 太さを数えない時にだけ数え違える幅)
        apart = next(room for room in range(width // 2, width * 2, 9144)
                     if LABEL.wraps(LONG, room - 2 * inset, stage, bold=True) > LABEL.wraps(LONG, room - 2 * inset, stage))
        self.assertEqual(LABEL.wraps(LONG, apart - 2 * inset, stage, bold=True) * LABEL.line_height(stage),
                         LABEL.caption_height(LONG, apart))

    def test_a_cell_keeps_room_for_the_name_so_its_picture_still_fills_the_width(self) -> None:
        """マスは絵の幅で決まる高さと名の行を取る。名の行を灰の小さい字で数えると、太字の名が絵の場所を食い、
        絵が縮んで細くなる。"""
        spec = {"type": "compose", "rows": [{"cells": [{"figure": "x.png", "caption": LONG}, {"text": "t"}]}]}
        self.assertEqual(picture(build(spec, DEFAULT)).rect.width, picture(build(spec, LABEL)).rect.width)

    def test_any_other_look_is_refused(self) -> None:
        with self.assertRaises(ThemeError):
            theme_from({"caption_look": "bold"})


if __name__ == "__main__":
    unittest.main()
