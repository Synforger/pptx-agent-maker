"""Lifts the rule "every page carries a figure" for the tests that are about something else.

Most tests build a page to look at its boxes, its stages or its table, not at its figure. A page of only
those parts is refused by the rule, and adding a picture to each would move every box the test measures.
So a test module runs with the rule lifted (= every page type may carry no figure) unless it says
`FIGURE_RULE_KEPT = True` at its top, which the tests of the rule itself and the corpus do.
"""

from __future__ import annotations

import pytest

from pptx_agent_maker.layout.types.core.registry import TYPES


@pytest.fixture(scope="module", autouse=True)
def figure_rule(request):
    """Run the module with every page type allowed to carry no figure, unless the module keeps the rule."""
    if getattr(request.module, "FIGURE_RULE_KEPT", False):
        yield
        return
    kept = dict(TYPES)
    for name, (filler, needs, takes, _figure) in kept.items():
        TYPES[name] = (filler, needs, takes, False)
    try:
        yield
    finally:
        TYPES.update(kept)
