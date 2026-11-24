"""The rule "every page carries a figure" holds for every test.

A module written when a page of words in boxes alone could be built is lifted out of it, by a line at its top:
`FIGURE_RULE_LIFTED = True`. Adding a picture to such a page would move every box the test measures. A test
written now is held by the rule, so nothing new runs outside it unseen; the modules that are lifted are the
ones `grep -l LIFTED tests` lists.

A module that tests what a page does with the extras alone (= cards, a table, a reading, a legend, with nothing
in the body) says `BARE_PAGE_TYPE = True` and gets the page type `bare`: a body that places nothing and may
carry no figure. It is a type of the tests only, so no module that lists the types sees it unasked.
"""

from __future__ import annotations

import sys

import pytest

#: Looked up, not imported: a run of a few tests that never touch a page type (= one `mutate` copy of the repo,
#: run without bytecode) should not pay to load them all.
REGISTRY = "pptx_agent_maker.layout.types.core.registry"


@pytest.fixture(scope="module", autouse=True)
def figure_rule(request):
    """Lift the rule of figures for a module that says so (= every page type may then carry no figure)."""
    registry = sys.modules.get(REGISTRY)
    if registry is None or not getattr(request.module, "FIGURE_RULE_LIFTED", False):
        yield
        return
    kept = dict(registry.TYPES)
    for name, (filler, needs, takes, _figure) in kept.items():
        registry.TYPES[name] = (filler, needs, takes, False)
    try:
        yield
    finally:
        registry.TYPES.update(kept)


def _place_nothing(page, spec, area) -> None:
    """The body of `bare`: nothing, so what a page adds under the cards sits right under them."""


@pytest.fixture(scope="module", autouse=True)
def bare_type(request):
    """Give a module that asks for it the type `bare` (= a body-less page that may carry no figure)."""
    registry = sys.modules.get(REGISTRY)
    if registry is None or not getattr(request.module, "BARE_PAGE_TYPE", False):
        yield
        return
    registry.register("bare", needs=[], figure=False)(_place_nothing)
    try:
        yield
    finally:
        registry.TYPES.pop("bare", None)
