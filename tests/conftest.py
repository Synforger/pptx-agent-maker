"""Lifts two rules for the tests that are about something else: "every page carries a figure", and the four
checks of how much a page asks of its reader (= `wordy_page`, `one_line_boxes`, `crowded_page`, `no_lead`).

Most tests build a page to look at its boxes, its stages or its table, not at its figure or its lead. A page of
only those parts is refused by the first rule and found by the second, and adding a picture to each would move
every box the test measures. So a test module runs with both lifted unless it says `FIGURE_RULE_KEPT = True` or
`PAGE_CHECKS_KEPT = True` at its top, which the tests of the rule and of the checks themselves do.
"""

from __future__ import annotations

import sys

import pytest

#: Looked up, not imported: a run of a few tests that never touch a page type (= one `mutate` copy of the repo,
#: run without bytecode) should not pay to load them all.
REGISTRY = "pptx_agent_maker.layout.types.core.registry"
CHECKS = "pptx_agent_maker.checks"
PAGE_CHECKS = frozenset({"wordy_page", "one_line_boxes", "crowded_page", "no_lead"})


@pytest.fixture(scope="module", autouse=True)
def figure_rule(request):
    """Run the module with every page type allowed to carry no figure, unless the module keeps the rule."""
    registry = sys.modules.get(REGISTRY)
    if registry is None or getattr(request.module, "FIGURE_RULE_KEPT", False):
        yield
        return
    kept = dict(registry.TYPES)
    for name, (filler, needs, takes, _figure) in kept.items():
        registry.TYPES[name] = (filler, needs, takes, False)
    try:
        yield
    finally:
        registry.TYPES.update(kept)


@pytest.fixture(scope="module", autouse=True)
def page_checks(request):
    """Run the module without the four checks of a page's weight, unless the module keeps them."""
    checks = sys.modules.get(CHECKS)
    if checks is None or getattr(request.module, "PAGE_CHECKS_KEPT", False):
        yield
        return
    kept = checks.DECLARED
    checks.DECLARED = tuple(check for check in kept if check.NAME not in PAGE_CHECKS)
    try:
        yield
    finally:
        checks.DECLARED = kept
