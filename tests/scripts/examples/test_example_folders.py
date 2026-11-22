"""The collection of examples is written inside the folder it is gathered in.

`task test:unit` runs it. Nothing is fetched.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .test_example_albums import examples


class ExampleFolders(unittest.TestCase):
    def setUp(self) -> None:
        kept = tempfile.TemporaryDirectory()
        self.addCleanup(kept.cleanup)
        self.base = Path(kept.name)
        self.to = self.base / "collection" / "slides-align"
        self.to.mkdir(parents=True)

    def gather(self, **changed: str) -> dict:
        entry = {"product": "Tool", "difficulty": "work_report", "topic": "A topic", "rank": 1, **changed}
        with mock.patch.object(examples, "tree", return_value=[]):
            return examples.fetch_deck(entry, self.to)

    def test_a_deck_lands_in_the_collection(self) -> None:
        self.assertEqual("slides-align/work_report/A_topic/1-Tool", self.gather()["path"])

    def test_a_folder_outside_the_collection_is_left_out(self) -> None:
        for changed in ({"difficulty": "../../outside"}, {"difficulty": str(self.base / "outside")},
                        {"product": "x/../../../../../outside"}):
            try:
                found = self.gather(**changed)
            except ValueError:
                found = {}
            self.assertTrue(found.get("missing"), changed)
            self.assertFalse((self.base / "outside").exists(), changed)
