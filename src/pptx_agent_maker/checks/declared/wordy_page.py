"""A declared page that holds more words than a reader takes in at a glance.

Words in boxes, cards, table cells, bands and notes are counted, not the title, the kicker, the sticker, the
source line or the page number, and not the figures and numbers a chart draws on its own axes.

The line is `WORDS_RED` words at `CHARS_PER_WORD` characters (spaces left out) each:
- 60 words is the red line an outside slide inspector (https://github.com/bayramannakov/ai-personal-os-skills,
  its slide-inspector) uses for a deck that is talked through while it is shown (40 is its yellow line).
- 2.0 is how many characters, spaces left out, one word came to in this toolkit's own README, read in English
  and in Japanese (1561 English words, 3156 Japanese characters).
"""

from __future__ import annotations

from .._internal.page_reading import characters, judged
from ..finding import Finding

NAME = "wordy_page"
READS_PAGES = True

WORDS_RED = 60
CHARS_PER_WORD = 2.0
#: the most characters a page may hold
LIMIT = round(WORDS_RED * CHARS_PER_WORD)


def off(config: dict | None) -> bool:
    """A project may switch the check off (= `[checks] wordy_page = false`)."""
    return (config or {}).get(NAME, True) is False


def why(count: int) -> str:
    return (f"{count} characters of words, {LIMIT} at most — say less on the page and more aloud: cut the words, "
            "move them to the notes, or let a picture or a chart carry them")


def run(manifest, theme=None, config: dict | None = None, pages: dict | None = None) -> list[Finding]:
    if off(config):
        return []
    return [Finding(NAME, number, title, why(characters(page)))
            for number, title, page in judged(manifest, pages) if characters(page) > LIMIT]
