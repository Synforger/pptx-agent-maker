"""Counting the pixels that differ between the pictures of two decks' pages.

ここが偽の 0 を出すと、「ほかの頁は変わっていない」を確かめるための道具が、変わった頁を
変わっていないと言う。数え落としと、無い頁を 0 で埋めることを見る。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "preview" / "src"))

from pptx_agent_maker.compare import compare_pictures, count_differing_pixels  # noqa: E402


def blank(size: tuple[int, int] = (10, 10)) -> Image.Image:
    return Image.new("RGB", size, (255, 255, 255))


def with_pixels(colour: tuple[int, int, int], *places: tuple[int, int]) -> Image.Image:
    picture = blank()
    for place in places:
        picture.putpixel(place, colour)
    return picture


class CountingDifferingPixels(unittest.TestCase):

    def test_equal_pictures_have_no_differing_pixel(self) -> None:
        self.assertEqual(count_differing_pixels(blank(), blank()), 0)

    def test_every_pixel_that_differs_is_counted_once(self) -> None:
        places = [(0, 0), (3, 4), (9, 9)]
        self.assertEqual(count_differing_pixels(blank(), with_pixels((0, 0, 0), *places)), len(places))

    def test_a_pixel_off_by_one_step_in_one_component_is_counted(self) -> None:
        # 灰色に直してから数えると、青の 1 段は 0 に丸まって数え落ちる
        for component in range(3):
            colour = [255, 255, 255]
            colour[component] = 254
            with self.subTest(component=component):
                self.assertEqual(count_differing_pixels(blank(), with_pixels(tuple(colour), (5, 5))), 1)


class ComparingTheirPages(unittest.TestCase):

    def test_each_page_is_counted_on_its_own(self) -> None:
        before = [blank(), blank(), blank()]
        after = [blank(), with_pixels((0, 0, 0), (1, 1), (2, 2)), blank()]
        found = compare_pictures(iter(before), iter(after))
        self.assertEqual([page.differing_pixels for page in found], [0, 2, 0])
        self.assertEqual([page.number for page in found], [1, 2, 3])
        self.assertEqual([page.is_changed for page in found], [False, True, False])

    def test_the_share_is_of_the_pixels_of_the_page(self) -> None:
        found = compare_pictures([blank()], [with_pixels((0, 0, 0), (0, 0))])
        self.assertEqual(found[0].pixel_count, 100)
        self.assertEqual(found[0].ratio, 0.01)

    def test_a_page_the_after_deck_lacks_is_said_to_be_missing_not_counted_as_zero(self) -> None:
        found = compare_pictures([blank(), blank(), blank()], [blank()])
        self.assertEqual(len(found), 3)
        for page in found[1:]:
            self.assertIsNone(page.after_size)
            self.assertIsNone(page.ratio, "a page that was not compared has no share to give")
            self.assertTrue(page.is_changed)
        self.assertFalse(found[0].is_changed)

    def test_a_page_the_before_deck_lacks_is_said_to_be_missing_too(self) -> None:
        found = compare_pictures([blank()], [blank(), blank()])
        self.assertIsNone(found[1].before_size)
        self.assertEqual(found[1].after_size, (10, 10))
        self.assertTrue(found[1].is_changed)

    def test_pages_drawn_at_another_size_are_not_laid_over_each_other(self) -> None:
        found = compare_pictures([blank((10, 10))], [blank((12, 10))])
        self.assertFalse(found[0].is_comparable)
        self.assertIsNone(found[0].ratio)
        self.assertTrue(found[0].is_changed)

    def test_pictures_are_taken_one_at_a_time(self) -> None:
        taken = []

        def pages(name: str):
            for _ in range(3):
                taken.append(name)
                yield blank()

        compare_pictures(pages("before"), pages("after"))
        self.assertEqual(taken, ["before", "after"] * 3, "all the pictures of one deck were held before the next began")


if __name__ == "__main__":
    unittest.main()
