"""The toolkit reads the XML parts of a deck with the same parser settings as python-pptx.

`task test:unit` runs it.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from pptx_agent_maker.deck.pages import text

SOURCE = Path(text.__file__).resolve().parents[2]
PART = """<?xml version="1.0"?>
<!DOCTYPE s [<!ENTITY word "spelled out">]>
<s xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:t>&word;</a:t></s>
"""


class XmlParts(unittest.TestCase):
    def test_an_entity_is_left_as_written(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            slide = Path(folder) / "slide1.xml"
            slide.write_text(PART, encoding="utf-8")
            self.assertEqual([], text.stand_in(slide, keep=set(), replace=[], names={}, hits={}))

    def test_every_part_read_from_a_deck_goes_through_the_shared_reader(self) -> None:
        bare = re.compile(r"etree\.(?:parse|fromstring)\((?!etree\.tostring|b\")")
        found = [f"{path.relative_to(SOURCE)}:{number}"
                 for path in sorted(SOURCE.rglob("*.py")) if path.name != "xml_part.py"
                 for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                 if bare.search(line)]
        self.assertEqual([], found)
