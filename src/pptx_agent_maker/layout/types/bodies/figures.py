"""Pictures as the body: one, several side by side, or a grid."""

from __future__ import annotations

from ...base.geometry import Rect
from ...parts.page import Page
from ..core.read import Spec
from ..core.registry import PageTypeError, register


@register("figure", needs=["figure"], takes=["caption"])
def _figure(page: Page, spec: Spec, area: Rect) -> None:
    """One image holding the body."""
    source, aspect = spec.figure()
    page.figure(area, source, aspect, caption=spec.text("caption"))


@register("figures", needs=["figures"])
def _figures(page: Page, spec: Spec, area: Rect) -> None:
    """Images side by side — the shape for comparing conditions."""
    items = spec.figures()
    if len(items) < 2:
        raise PageTypeError("figures: put at least two images side by side, or use `figure`")
    for cell, (source, aspect, caption) in zip(
            area.columns(len(items), gap=page.theme.spacing.gap_m), items):
        page.figure(cell, source, aspect, caption=caption)


@register("figure_grid", needs=["figures"], takes=["columns"])
def _figure_grid(page: Page, spec: Spec, area: Rect) -> None:
    """Images on a grid — two axes at once (= item × method)."""
    items = spec.figures()
    columns = int(spec.get("columns", 3))
    if columns < 1:
        raise PageTypeError("figure_grid: `columns` must be at least 1")
    rows = -(-len(items) // columns)
    cells = [cell for band in area.grid(rows, columns, gap=page.theme.spacing.gap_s)
             for cell in band]
    for cell, (source, aspect, caption) in zip(cells, items):
        page.figure(cell, source, aspect, caption=caption)
