"""A chart drawn from its numbers, which a person can still edit in PowerPoint: `chart`.

**伝えたいことが図を決める。**比べるなら棒、移り変わりなら折れ線、内訳なら積み上げ、増減の積み重ねなら
滝グラフ ― 5 つで足りる。絵で貼ったグラフは、数字が 1 つ変わるたびに描き直しになり、渡した先では
誰も直せない。ここで書くグラフは数字を deck の中に持ち、PowerPoint の「データの編集」で直せる。

見た目は決まっている (= 頁が選べるのは、どの 1 つを目立たせるかだけ):

* **目を集めるのは 1 つ。**`highlight` に書いた系列か項目だけが差し色で、ほかは灰
* **値の数字は棒に付ける。**目盛りの線は引かず、数字を付けたグラフは値の軸も出さない
  (= 同じ数を 2 度見せない)。`labels = false` なら数字を付けず、値の軸が出る
* **凡例は系列が 2 つ以上の時だけ**
* 字の大きさは本文の大きさ、書体は頁と同じ

数は manifest に書くか、素材の folder の CSV から読む (= `data = "x.csv"`。1 列目が項目、2 列目からが
系列、1 行目が系列の名前)。

⚠ **組み合わせのグラフ (= 棒と折れ線) は無い。**書き出す口が無く、2 つの読みを 1 枚に載せることにもなる。
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ...base.geometry import Rect
from ...parts.elements import Chart, Series
from ...parts.look import TONES
from ...parts.page import Page
from ..core.read import Spec, only_keys, read_tone
from ..core.registry import PageTypeError, register

#: グラフの種類。`bar` は横棒、`column` は縦棒、`stacked` は積み上げた縦棒、`waterfall` は滝グラフ
KINDS = ("bar", "column", "line", "stacked", "waterfall")
#: グラフが読むキー
KEYS = ("kind", "categories", "series", "data", "highlight", "unit", "labels", "totals")
#: 系列が読むキー
SERIES_KEYS = ("name", "values", "tone")

#: `highlight` も `tone` も書かない系列の色の役、書いた順 (= 最初の系列が主役で、続きは灰の濃淡)。
#: 見分けられる灰はこの 2 つまでなので、4 つめからの系列は自分で `tone` を書く
UNSAID = ("accent", "muted", "rule")


@dataclass(frozen=True)
class _Plan:
    """What the manifest wrote, checked."""

    kind: str
    categories: tuple[str, ...]
    #: (名前, 値, 書かれた色の役 ― 書かなければ空)
    series: tuple[tuple[str, tuple[float, ...], str], ...]
    highlight: str
    unit: str
    labels: bool
    totals: tuple[str, ...]


@register("chart", needs=["chart"])
def _chart(page: Page, spec: Spec, area: Rect) -> None:
    """One chart holding the body."""
    place_chart(page, spec, spec.get("chart"), area, "chart")


def place_chart(page: Page, spec: Spec, written, rect: Rect, what: str) -> None:
    """Read a chart as written and put it in `rect` (= as a page's body, or in a cell of a compose)."""
    plan = _read(spec, written, what)
    theme, palette = page.theme, page.theme.palette
    series, legend = (_waterfall(page, plan, what) if plan.kind == "waterfall" else _plain(page, plan, what))
    page.chart(Chart(
        "chart", rect, "stacked" if plan.kind == "waterfall" else plan.kind, plan.categories, series,
        size=theme.type.body, colour=palette.ink, line=palette.rule, legend=legend, axis=not plan.labels))


# -- reading ---------------------------------------------------------------------


def _read(spec: Spec, written, what: str) -> _Plan:
    only_keys(written, set(KEYS), what)
    kind = written.get("kind")
    if kind not in KINDS:
        raise PageTypeError(f"{what}: `kind` is one of {', '.join(KINDS)}, not {kind!r}")
    if "data" in written:
        if "categories" in written or "series" in written:
            raise PageTypeError(f"{what}: the numbers come from `data` or from `categories` and `series`, "
                                "not from both")
        categories, series = _from_file(spec, written["data"], what)
    else:
        categories, series = _written(spec, written, what)
    if len(set(categories)) != len(categories):
        raise PageTypeError(f"{what}: a category is written twice — each has a name of its own")
    names = [name for name, _values, _tone in series]
    if len(set(names)) != len(names):
        raise PageTypeError(f"{what}: a series is written twice — each has a name of its own")

    highlight = written.get("highlight", "")
    if not isinstance(highlight, str):
        raise PageTypeError(f"{what}: `highlight` is the name of one series or one category, not {highlight!r}")
    unit = written.get("unit", "")
    if not isinstance(unit, str) or '"' in unit:
        raise PageTypeError(f"{what}: `unit` is a few characters written after each number "
                            f"(= with no double quote), not {unit!r}")
    labels = written.get("labels", True)
    if not isinstance(labels, bool):
        raise PageTypeError(f"{what}: `labels` is true or false, not {labels!r}")
    totals = written.get("totals", [])
    if kind != "waterfall" and "totals" in written:
        raise PageTypeError(f"{what}: `totals` belongs to a waterfall, and this is a {kind}")
    if not isinstance(totals, list) or any(str(name) not in categories for name in totals):
        raise PageTypeError(f"{what}: `totals` lists the categories that are totals (= bars that stand on "
                            f"the ground), each by its name; the categories are {', '.join(categories)}")
    return _Plan(kind, tuple(categories), tuple(series), highlight, unit, labels,
                 tuple(str(name) for name in totals))


def _number(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PageTypeError(f"{where} is {value!r} — a chart is drawn from numbers")
    return value


def _written(spec: Spec, written: dict, what: str):
    """The categories and the series, written in the manifest itself."""
    categories = written.get("categories")
    if not isinstance(categories, list) or not categories or any(not str(name).strip() for name in categories):
        raise PageTypeError(f"{what}: `categories` is the list of what the numbers are for, each with a name "
                            "(= or give `data`, a CSV among the assets)")
    categories = [str(name) for name in categories]
    listed = written.get("series")
    if not isinstance(listed, list) or not listed:
        raise PageTypeError(f"{what}: `series` is a list of {{ name = …, values = […] }}, at least one")
    series = []
    for number, item in enumerate(listed, start=1):
        where = f"{what}: series {number}"
        only_keys(item, set(SERIES_KEYS), where)
        name = str(item.get("name", "")).strip()
        if not name:
            raise PageTypeError(f"{where} has no `name` — it heads the column of numbers a person edits")
        values = item.get("values")
        if not isinstance(values, list) or len(values) != len(categories):
            raise PageTypeError(f"{where} ({name}): `values` has one number for each of the "
                                f"{len(categories)} categories")
        tone = read_tone(spec, item, where, "") if "tone" in item else ""
        series.append((name, tuple(_number(value, f"{where} ({name}), value {index}")
                                   for index, value in enumerate(values, start=1)), tone))
    return categories, series


def _from_file(spec: Spec, name, what: str):
    """The categories and the series, read from a CSV among the assets.

    1 列目が項目、2 列目からが系列。1 行目は系列の名前 (= 左上のマスは読まない)。
    """
    if not isinstance(name, str) or Path(name).suffix.lower() != ".csv":
        raise PageTypeError(f"{what}: `data` is the name of a CSV file among the assets, not {name!r}")
    path = spec.asset(name)
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.reader(handle) if any(cell.strip() for cell in row)]
    if len(rows) < 2 or len(rows[0]) < 2:
        raise PageTypeError(f"{what}: {name} needs a first row naming the series and a first column naming "
                            "the categories, with numbers in between")
    names = [cell.strip() for cell in rows[0][1:]]
    if any(not cell for cell in names):
        raise PageTypeError(f"{what}: {name}, row 1 names every series — one of the names is empty")
    categories, columns = [], [[] for _name in names]
    for number, row in enumerate(rows[1:], start=2):
        if len(row) != len(rows[0]) or not row[0].strip():
            raise PageTypeError(f"{what}: {name}, row {number} has {len(row)} cells and the first row has "
                                f"{len(rows[0])} — a category, then one number for each series")
        categories.append(row[0].strip())
        for column, cell in enumerate(row[1:], start=2):
            try:
                value = int(cell) if cell.strip().lstrip("+-").isdigit() else float(cell)
            except ValueError:
                raise PageTypeError(f"{what}: {name}, row {number}, column {column} is {cell!r} — "
                                    "a chart is drawn from numbers") from None
            columns[column - 2].append(_number(value, f"{what}: {name}, row {number}, column {column}"))
    return categories, [(series, tuple(values), "") for series, values in zip(names, columns)]


# -- drawing ---------------------------------------------------------------------


def _places(values) -> int:
    """How many decimal places the numbers are written to (= the most any of them has)."""
    return max((max(-Decimal(str(value)).normalize().as_tuple().exponent, 0) for value in values), default=0)


def _format(plan: _Plan, sign: str = "") -> str:
    """How a value is printed beside its bar: thousands apart, the places written, then the unit."""
    places = _places(value for _name, values, _tone in plan.series for value in values)
    number = "#,##0" + ("." + "0" * places if places else "")
    unit = f'"{plan.unit}"' if plan.unit else ""
    # 符号を自分で書く書式は、正と負の両方に同じ符号を言う (= 棒の向きではなく、増えたか減ったかを書く)
    return f"{sign}{number}{unit};{sign}{number}{unit}" if sign else f"{number}{unit}"


def _plain_number(value: Decimal) -> float:
    """A number worked out exactly, as the whole number or the fraction it is."""
    return int(value) if value == value.to_integral_value() else float(value)


def _plain(page: Page, plan: _Plan, what: str) -> tuple[tuple[Series, ...], bool]:
    """Bars, columns, lines and stacked columns: the series as written, each in its colour."""
    palette = page.theme.palette
    names = [name for name, _values, _tone in plan.series]
    toned = [name for name, _values, tone in plan.series if tone]
    one_series = one_category = None
    if plan.highlight:
        if toned:
            raise PageTypeError(f"{what}: `highlight` already says which one stands out — "
                                f"take the `tone` off {', '.join(toned)}")
        in_series, in_categories = plan.highlight in names, plan.highlight in plan.categories
        if in_series and in_categories:
            raise PageTypeError(f"{what}: `highlight` is {plan.highlight!r}, which names both a series and a "
                                "category — give one of them another name")
        if not in_series and not in_categories:
            raise PageTypeError(f"{what}: `highlight` is {plan.highlight!r}, which is neither a series "
                                f"({', '.join(names)}) nor a category ({', '.join(plan.categories)})")
        if in_categories and len(names) > 1:
            raise PageTypeError(f"{what}: with {len(names)} series, `highlight` names one of them "
                                f"({', '.join(names)}) — a category stands out only where there is one series")
        one_series = plan.highlight if in_series else None
        one_category = plan.categories.index(plan.highlight) if in_categories else None

    number_format = _format(plan) if plan.labels else ""
    drawn = []
    for index, (name, values, tone) in enumerate(plan.series):
        if plan.highlight:
            colour = palette.accent if name == one_series else palette.muted
        elif tone:
            colour = page.ground(tone)[0]
        elif index < len(UNSAID):
            colour = getattr(palette, UNSAID[index])
        else:
            raise PageTypeError(
                f"{what}: series {index + 1} ({name}) has no colour of its own — past the first "
                f"{len(UNSAID)}, give each series a `tone` ({', '.join(TONES)}), or `highlight` one")
        stacked = plan.kind == "stacked"
        drawn.append(Series(
            name, values, colour,
            points=((one_category, palette.accent),) if one_category is not None else (),
            number_format=number_format,
            # 段の中に置く数字は、その段の地の上で読める方の色。段の境は紙の色の細い線で切る
            label_colour=palette.words_on(colour) if stacked else "",
            outline=palette.paper if stacked else ""))
    return tuple(drawn), len(drawn) > 1


def _waterfall(page: Page, plan: _Plan, what: str) -> tuple[tuple[Series, ...], bool]:
    """A waterfall: each step floats where the one before it ended, on columns stacked over a hidden base.

    書くのは増減の値だけ (= 1 つの系列)。`totals` に名前を書いた項目は合計の棒で、地面から立つ ― 最初の
    項目なら出発点の値、途中や最後なら、そこまでの増減を足した値と同じでなければならない (= 食い違う
    数字を載せない)。棒を浮かせる台と、増えた・減った・合計の振り分けは道具が計算する。

    ⚠ **1 つの段が 0 をまたぐ滝グラフは描けない** (= 台は 0 の片側にしか積めない)。0 で 2 段に分ける。
    """
    palette = page.theme.palette
    if len(plan.series) != 1:
        raise PageTypeError(f"{what}: a waterfall is drawn from one series of steps, and {len(plan.series)} "
                            "are written")
    if plan.highlight or plan.series[0][2]:
        raise PageTypeError(f"{what}: a waterfall's colours say what each bar is (= up, down, a total) — "
                            "it takes no `highlight` and no `tone`")
    name, values, _tone = plan.series[0]
    base, up, down, total = [], [], [], []
    # 書かれた桁のまま足す (= 0.1 を 3 回足して 0.3 にならない足し算では、合計の照合も 0 の判定も狂う)
    running = Decimal(0)
    for index, (category, value) in enumerate(zip(plan.categories, values)):
        step = Decimal(str(value))
        if category in plan.totals:
            if index and step != running:
                raise PageTypeError(
                    f"{what}: {category!r} is written as {value:g}, and the steps before it add up to "
                    f"{float(running):g} — a total says what the steps come to")
            running = step
            base.append(None), up.append(None), down.append(None), total.append(value)
            continue
        before, running = running, running + step
        if before * running < 0:
            raise PageTypeError(
                f"{what}: the step {category!r} goes from {float(before):g} to {float(running):g}, across "
                "zero — write it as two steps that meet at zero")
        # 0 より上の段は低い方の端を台にして上へ、0 より下の段は高い方の端を台にして下へ積む
        below = before < 0 or running < 0
        foot = max(before, running) if below else min(before, running)
        base.append(_plain_number(foot) if foot else None)
        tall = -abs(value) if below else abs(value)
        up.append(tall if value >= 0 else None), down.append(tall if value < 0 else None), total.append(None)

    def labelled(sign: str, colour: str) -> dict:
        return {"number_format": _format(plan, sign) if plan.labels else "", "label_colour": palette.words_on(colour)}

    return (
        Series("(base)", tuple(base)),
        Series(f"{name} +", tuple(up), palette.good, **labelled("+", palette.good)),
        Series(f"{name} -", tuple(down), palette.bad, **labelled("-", palette.bad)),
        Series(f"{name} =", tuple(total), palette.accent, **labelled("", palette.accent)),
    ), False
