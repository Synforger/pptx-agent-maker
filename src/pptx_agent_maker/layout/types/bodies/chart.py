"""A chart drawn from its numbers, which a person can still edit in PowerPoint: `chart`.

**伝えたいことが図を決める。**比べるなら棒、移り変わりなら折れ線、内訳なら積み上げ、増減の積み重ねなら
滝グラフ、2 つの量の関係なら点 (= 散布図) ― 6 つで足りる。絵で貼ったグラフは、数字が 1 つ変わるたびに描き直しになり、渡した先では
誰も直せない。ここで書くグラフは数字を deck の中に持ち、PowerPoint の「データの編集」で直せる。

見た目は決まっている (= 頁が選べるのは、どの 1 つを目立たせるかだけ):

* **目を集めるのは 1 つ。**`highlight` に書いた系列か項目だけが差し色で、ほかは灰
* **値の数字は棒に付ける。**目盛りの線は引かず、数字を付けたグラフは値の軸も出さない
  (= 同じ数を 2 度見せない)。`labels = false` なら数字を付けず、値の軸が出る
* **凡例は系列が 2 つ以上の時だけ**
* 字の大きさは本文の大きさ、書体は頁と同じ

数は manifest に書くか、素材の folder の CSV から読む (= `data = "x.csv"`。1 列目が項目、2 列目からが
系列、1 行目が系列の名前)。

点のグラフ (= `scatter`) だけは数の形が違う ― 項目を持たず、系列は点 (= x と y の 1 組) の集まり。軸が何かを
言わない散布図は読めないので、軸の名前 (= `x` と `y`) を必ず書く。CSV は 1 列目が x、2 列目からが系列の y。

グラフの 1 点を指す注記は `callouts` に、**どの項目のどの系列か**で書く (= 座標は書かない)。点の位置は
道具が計算し、言葉をグラフの外 (= 縦のグラフは上、横棒は右) に、細い線を点まで置く。そのために、
注記を持つグラフだけは、描く範囲と値の軸を道具が決めて書き出す。

⚠ **組み合わせのグラフ (= 棒と折れ線) は無い。**書き出す口が無く、2 つの読みを 1 枚に載せることにもなる。
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ...base.geometry import Rect
from ...parts.elements import Callout, Chart, Pinned, Series
from ...parts.look import TONES
from ...parts.page import Page, PageFullError
from ..core.read import Spec, only_keys, read_tone
from ..core.registry import PageTypeError, register

#: グラフの種類。`bar` は横棒、`column` は縦棒、`stacked` は積み上げた縦棒、`waterfall` は滝グラフ、
#: `scatter` は点 (= 2 つの量の関係)
KINDS = ("bar", "column", "line", "stacked", "waterfall", "scatter")
#: グラフが読むキー
KEYS = ("kind", "categories", "series", "data", "highlight", "unit", "labels", "totals", "callouts", "x", "y")
#: 点のグラフが読むキー (= 項目も、棒に付ける数字も、柱を指す注記も持たない)
POINT_KEYS = ("kind", "x", "y", "series", "data", "highlight")
#: 点のグラフの系列が読むキー
POINT_SERIES_KEYS = ("name", "points", "tone")
#: 注記が読むキー (= どの項目の、どの系列を指して、何と言うか)
CALLOUT_KEYS = ("at", "series", "text")
#: 注記が柱 1 本を丸ごと指す種類 (= 系列を名指ししない)。積み上げの中の段を上から指すと、線が上の段と
#: その数字を突き抜ける
WHOLE = ("stacked", "waterfall")
#: 項目どうしの間 (= 棒 1 本の幅に対する百分率)。PowerPoint の既定と同じ値を、注記を持つグラフには
#: 書き出す ― 棒の位置を計算するのに、書いていない既定には頼らない
GAP = 150
#: 系列が読むキー
SERIES_KEYS = ("name", "values", "tone", "points")

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
    #: (項目の番号, 系列の番号, 言葉)
    callouts: tuple[tuple[int, int, str], ...] = ()


@register("chart", needs=["chart"])
def _chart(page: Page, spec: Spec, area: Rect) -> None:
    """One chart holding the body."""
    place_chart(page, spec, spec.get("chart"), area, "chart")


def place_chart(page: Page, spec: Spec, written, rect: Rect, what: str) -> None:
    """Read a chart as written and put it in `rect` (= as a page's body, or in a cell of a compose)."""
    theme, palette = page.theme, page.theme.palette
    # どのグラフも同じ: 字は本文の大きさと色、軸の線は区切りの線の色
    look = dict(size=theme.type.body, colour=palette.ink, line=palette.rule)
    if isinstance(written, dict) and written.get("kind") == "scatter":
        titles, series = _points(page, spec, written, what)
        page.chart(Chart("chart", rect, "scatter", (), series, legend=len(series) > 1, axis=True,
                         x_title=titles[0], y_title=titles[1], **look))
        return
    plan = _read(spec, written, what)
    series, legend = (_waterfall(page, plan, what) if plan.kind == "waterfall" else _plain(page, plan, what))
    frame, pinned, callouts = _pointed(page, plan, rect, legend, what) if plan.callouts else (None, None, ())
    page.chart(Chart(
        "chart", rect, "stacked" if plan.kind == "waterfall" else plan.kind, plan.categories, series,
        legend=legend, axis=not plan.labels, frame=frame, pinned=pinned, callouts=callouts, **look))


# -- reading ---------------------------------------------------------------------


def _read(spec: Spec, written, what: str) -> _Plan:
    only_keys(written, set(KEYS), what)
    kind = written.get("kind")
    if kind not in KINDS:
        raise PageTypeError(f"{what}: `kind` is one of {', '.join(KINDS)}, not {kind!r}")
    named = [axis for axis in ("x", "y") if axis in written]
    if named:
        raise PageTypeError(f"{what}: {' and '.join(f'`{axis}`' for axis in named)} name the axes of a scatter, "
                            f"and this is a {kind} — its categories say what it is drawn across")
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
                 tuple(str(name) for name in totals),
                 _callouts(written.get("callouts"), kind, categories, names, what))


def _callouts(listed, kind: str, categories: list[str], names: list[str], what: str):
    """The callouts as written: each names a category, the series when there are several, and its words."""
    if listed is None:
        return ()
    if not isinstance(listed, list) or not listed:
        raise PageTypeError(f"{what}: `callouts` is a list of {{ at = …, text = … }}, at least one")
    found = []
    for number, item in enumerate(listed, start=1):
        where = f"{what}: callout {number}"
        only_keys(item, set(CALLOUT_KEYS), where)
        at, text = item.get("at"), item.get("text")
        if str(at) not in categories:
            raise PageTypeError(f"{where}: `at` is {at!r} — it names the category the words point at "
                                f"({', '.join(categories)})")
        if not isinstance(text, str) or not text.strip() or "\n" in text:
            raise PageTypeError(f"{where}: `text` is the few words to say, on one line")
        if kind in WHOLE and "series" in item:
            raise PageTypeError(f"{where}: a {kind} chart is pointed at one column at a time — `at` alone "
                                "says which; say which part of it in the words")
        if "series" not in item and len(names) > 1 and kind not in WHOLE:
            raise PageTypeError(f"{where}: with {len(names)} series, say which one with `series` "
                                f"({', '.join(names)})")
        if "series" in item and str(item["series"]) not in names:
            raise PageTypeError(f"{where}: `series` is {item['series']!r} — the series are {', '.join(names)}")
        point = (categories.index(str(at)), names.index(str(item["series"])) if "series" in item else 0)
        if point in [(category, series) for category, series, _text in found]:
            raise PageTypeError(f"{where}: {at!r} already has a callout — one point takes one")
        found.append((*point, text.strip()))
    return tuple(found)


def _number(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PageTypeError(f"{where} is {value!r} — a chart is drawn from numbers")
    return value


def _cell(cell: str, where: str):
    """A number as a CSV holds it: a whole number stays one (= it is printed without a decimal point)."""
    try:
        value = int(cell) if cell.strip().lstrip("+-").isdigit() else float(cell)
    except ValueError:
        raise PageTypeError(f"{where} is {cell!r} — a chart is drawn from numbers") from None
    return _number(value, where)


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
        if "points" in item:
            raise PageTypeError(f"{where} ({name}): `points` belong to a scatter — a {written.get('kind')} "
                                "has one number for each category, in `values`")
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
            columns[column - 2].append(_cell(cell, f"{what}: {name}, row {number}, column {column}"))
    return categories, [(series, tuple(values), "") for series, values in zip(names, columns)]


# -- a chart of points -----------------------------------------------------------


def _points(page: Page, spec: Spec, written: dict, what: str):
    """A scatter as written, checked: (the names of its two axes), the series as they are drawn."""
    unknown = sorted(set(written) - set(POINT_KEYS))
    if unknown:
        raise PageTypeError(
            f"{what}: a scatter does not take {', '.join(unknown)} (= it takes {', '.join(POINT_KEYS)}) — "
            "it has no categories, no number beside a bar and no column to point at")
    titles = []
    for axis in ("x", "y"):
        title = written.get(axis)
        if not isinstance(title, str) or not title.strip():
            raise PageTypeError(f"{what}: `{axis}` is the name of the {axis} axis, with its unit — "
                                "a scatter that does not say what its axes are cannot be read")
        titles.append(title.strip())
    if "data" in written:
        if "series" in written:
            raise PageTypeError(f"{what}: the numbers come from `data` or from `series`, not from both")
        series = _points_from_file(spec, written["data"], what)
    else:
        series = _points_written(spec, written, what)
    names = [name for name, _points_, _tone in series]
    if len(set(names)) != len(names):
        raise PageTypeError(f"{what}: a series is written twice — each has a name of its own")
    highlight = written.get("highlight", "")
    if not isinstance(highlight, str) or (highlight and highlight not in names):
        raise PageTypeError(f"{what}: `highlight` is {highlight!r}, which is not one of the series "
                            f"({', '.join(names)})")
    toned = [name for name, _points_, tone in series if tone]
    if highlight and toned:
        raise PageTypeError(f"{what}: `highlight` already says which one stands out — "
                            f"take the `tone` off {', '.join(toned)}")
    drawn = []
    for index, (name, points, tone) in enumerate(series):
        colour, _edge = _series_colour(page, index, name, tone, (name == highlight) if highlight else None, what)
        drawn.append(Series(name, tuple(y for _x, y in points), colour, xs=tuple(x for x, _y in points)))
    return tuple(titles), tuple(drawn)


def _points_written(spec: Spec, written: dict, what: str):
    listed = written.get("series")
    if not isinstance(listed, list) or not listed:
        raise PageTypeError(f"{what}: `series` is a list of {{ name = …, points = [[x, y], …] }}, at least one")
    series = []
    for number, item in enumerate(listed, start=1):
        where = f"{what}: series {number}"
        if isinstance(item, dict) and "values" in item:
            raise PageTypeError(f"{where}: a scatter is drawn from `points` (= [[x, y], …]), not from `values`")
        only_keys(item, set(POINT_SERIES_KEYS), where)
        name = str(item.get("name", "")).strip()
        if not name:
            raise PageTypeError(f"{where} has no `name` — it heads the column of numbers a person edits")
        points = item.get("points")
        if (not isinstance(points, list) or not points
                or any(not isinstance(point, list) or len(point) != 2 for point in points)):
            raise PageTypeError(f"{where} ({name}): `points` is a list of [x, y], at least one")
        tone = read_tone(spec, item, where, "") if "tone" in item else ""
        series.append((name, tuple(
            (_number(x, f"{where} ({name}), `points` {index}, x"), _number(y, f"{where} ({name}), `points` {index}, y"))
            for index, (x, y) in enumerate(points, start=1)), tone))
    return series


def _points_from_file(spec: Spec, name, what: str):
    """The points of a scatter, read from a CSV among the assets.

    1 列目が x、2 列目からが系列の y。1 行目は系列の名前 (= 左上のマスは読まない)。空のマスは
    「その系列は、この x に点を持たない」。
    """
    if not isinstance(name, str) or Path(name).suffix.lower() != ".csv":
        raise PageTypeError(f"{what}: `data` is the name of a CSV file among the assets, not {name!r}")
    with Path(spec.asset(name)).open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.reader(handle) if any(cell.strip() for cell in row)]
    if len(rows) < 2 or len(rows[0]) < 2:
        raise PageTypeError(f"{what}: {name} needs a first row naming the series and a first column of x, "
                            "with each series' y beside it")
    names = [cell.strip() for cell in rows[0][1:]]
    if any(not cell for cell in names):
        raise PageTypeError(f"{what}: {name}, row 1 names every series — one of the names is empty")

    def number(cell: str, row: int, column: int) -> float:
        return _cell(cell, f"{what}: {name}, row {row}, column {column}")

    points: list[list[tuple[float, float]]] = [[] for _name in names]
    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) != len(rows[0]):
            raise PageTypeError(f"{what}: {name}, row {row_number} has {len(row)} cells and the first row has "
                                f"{len(rows[0])} — an x, then a y (or nothing) for each series")
        x = number(row[0], row_number, 1)
        for column, cell in enumerate(row[1:], start=2):
            if cell.strip():
                points[column - 2].append((x, number(cell, row_number, column)))
    empty = [series for series, found in zip(names, points) if not found]
    if empty:
        raise PageTypeError(f"{what}: {name} gives {', '.join(empty)} no point at all")
    return [(series, tuple(found), "") for series, found in zip(names, points)]


# -- drawing ---------------------------------------------------------------------


def _series_colour(page: Page, index: int, name: str, tone: str, standing_out: bool | None,
                   what: str) -> tuple[str, str]:
    """(the colour, the edge) of one series, by the rule every chart shares.

    `standing_out` は、グラフが `highlight` を持つ時だけ言う (= この系列がその 1 つか)。持たなければ、
    書いた `tone`、書かなければ順番で決まる色 (= 最初が主役、続きは灰の濃淡)。
    """
    palette = page.theme.palette
    if standing_out is not None:
        return (palette.accent if standing_out else palette.muted), ""
    if tone:
        # 薄い地の系列は、箱と同じく地を濃くした色の枠を持つ (= 紙の上で棒の端が読める)
        colour, _words, edge = page.ground(tone)
        return colour, edge
    if index < len(UNSAID):
        return getattr(palette, UNSAID[index]), ""
    raise PageTypeError(
        f"{what}: series {index + 1} ({name}) has no colour of its own — past the first "
        f"{len(UNSAID)}, give each series a `tone` ({', '.join(TONES)}), or `highlight` one")


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
        colour, edge = _series_colour(page, index, name, tone,
                                      (name == one_series) if plan.highlight else None, what)
        stacked = plan.kind == "stacked"
        drawn.append(Series(
            name, values, colour,
            points=((one_category, palette.accent),) if one_category is not None else (),
            number_format=number_format,
            # 段の中に置く数字は、その段の地の上で読める方の色。段の境は紙の色の細い線で切る
            label_colour=palette.words_on(colour) if stacked else "",
            outline=edge or (palette.paper if stacked else "")))
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


# -- pointing at a point ---------------------------------------------------------


def _printed(plan: _Plan, value: float) -> str:
    """A value as it is printed beside its bar (= the same places and unit as `_format`)."""
    places = _places(value for _name, values, _tone in plan.series for value in values)
    return f"{value:,.{places}f}{plan.unit}"


def _tops(plan: _Plan) -> list[list[tuple[float, float]]]:
    """For every category and series: where its bar (or point) ends, and how far the stack reaches there.

    返すのは項目ごと・系列ごとの (その棒の先の値, その項目でいちばん遠くまで届く値)。
    """
    found = []
    if plan.kind == "waterfall":
        running = Decimal(0)
        for category, value in zip(plan.categories, plan.series[0][1]):
            before = running
            running = Decimal(str(value)) if category in plan.totals else running + Decimal(str(value))
            top = float(running) if category in plan.totals else float(max(before, running))
            found.append([(max(top, 0.0), max(top, 0.0))])
        return found
    for index in range(len(plan.categories)):
        column = [values[index] for _name, values, _tone in plan.series]
        if plan.kind == "stacked":
            reach = float(sum(max(value, 0) for value in column))      # 柱の頭 (= 正の値を積んだ先)
            found.append([(reach, reach)] * len(column))
        else:
            found.append([(value if plan.kind == "line" else max(value, 0), value) for value in column])
    return found


def _nice(span: float) -> float:
    """A step of 1, 2 or 5 times a power of ten, about five to the span."""
    rough = span / 5
    power = 10 ** math.floor(math.log10(rough))
    return next(step * power for step in (1, 2, 5, 10) if step * power >= rough)


def _pointed(page: Page, plan: _Plan, rect: Rect, legend: bool, what: str):
    """Where the plot is held, and where each callout's words and line go.

    言葉はグラフの外に置く ― 縦のグラフは上の帯に、点の真上へ。横棒は右の帯に、棒の高さへ。線は言葉から
    点の手前 (= 棒に付いた数字の外) まで。**言葉どうしが重なるなら止まる** (= 縮めない、ずらさない)。

    点の位置は、描く範囲 (= `inner`) と値の軸の端を道具が決めるので計算できる:
    項目は描く範囲を等分し、棒は項目の幅を「系列の数 + 項目どうしの間」で割った幅で並ぶ。
    """
    theme, s = page.theme, page.theme.spacing
    line, pad = theme.line_height(), s.gap_s
    across = plan.kind == "bar"                      # 値が横に伸びるグラフ
    outside = plan.labels and plan.kind in ("bar", "column", "line")   # 数字が棒の外に付く
    tops = _tops(plan)
    names = [text for _category, _series, text in plan.callouts]
    wide = [theme.width(text) for text in names]

    # 1. 言葉の帯を除いた残りがグラフの枠
    if across:
        band = max(wide) + s.gap_s
        frame = Rect(rect.left, rect.top, rect.width - band, rect.height)
    else:
        band = line + s.gap_s
        frame = Rect(rect.left, rect.top + band, rect.width, rect.height - band)

    # 2. 枠の中の描く範囲 (= 軸の字と凡例の場所を除く)
    below = (line + s.gap_s if legend else 0)
    low, high = min(0.0, *(value for column in tops for _top, value in column)), \
        max(0.0, *(reach for column in tops for _top, reach in column))
    longest = max((theme.width(name) for name in plan.categories), default=0)
    if across:
        left = frame.left + pad + longest + s.gap_s
        top, bottom = frame.top + pad, frame.bottom - pad - below - (0 if plan.labels else line + s.gap_s)
        right = frame.right - pad
    else:
        left = frame.left + pad                       # 値の軸の字の幅は、目盛りが決まってから足す
        top, bottom = frame.top + max(pad, line // 2), frame.bottom - (line + s.gap_s) - below
        right = frame.right - pad
    if right - left <= 0 or bottom - top <= 0:
        raise PageFullError(f"{what}: the chart has no room left for its plot beside its callouts and its "
                            "labels — give it more room, or say less")

    # 3. 値の軸の端 ― 棒の外に付く数字のぶんを、いちばん遠い棒の先に空ける
    reach = (right - left) if across else (bottom - top)
    room = (max(theme.width(_printed(plan, value)) for _n, values, _t in plan.series for value in values)
            + s.gap_s if across else line + s.bar_pad_y) if outside else 0
    share = room / reach
    if share >= 0.5:
        raise PageFullError(f"{what}: the numbers on the bars would take half the plot — more room, or "
                            "`labels = false`")
    span = (high - low) or 1.0
    high = high + span * share / (1 - share * (2 if low < 0 else 1)) if high > 0 else high
    low = low - span * share / (1 - 2 * share) if low < 0 else low
    step = _nice(high - low)
    high, low = math.ceil(round(high / step, 9)) * step, math.floor(round(low / step, 9)) * step
    if not across and not plan.labels:
        ticks = [low + step * index for index in range(round((high - low) / step) + 1)]
        left += max(theme.width(f"{tick:,g}") for tick in ticks) + s.gap_s
        if right - left <= 0:
            raise PageFullError(f"{what}: the chart has no room left for its plot")
    inner = Rect(left, top, right - left, bottom - top)

    # 4. 点の位置
    count, members = len(plan.categories), (1 if plan.kind in (*WHOLE, "line") else len(plan.series))

    def along(category: int, series: int, extent: int) -> float:
        """How far along the category axis a bar's middle sits (= 0 at its start, `extent` at its end)."""
        slot = extent / count
        if plan.kind == "line" or members == 1:
            return slot * (category + 0.5)
        bar = slot / (members + GAP / 100)
        return slot * category + bar * (GAP / 200 + series + 0.5)

    def toward(value: float, extent: int) -> float:
        return extent * (value - low) / (high - low)

    placed = []
    for (category, series, text), width in zip(plan.callouts, wide):
        tip = tops[category][series][0]
        if across:
            x = inner.left + toward(tip, inner.width)
            y = inner.top + along(category, series, inner.height)
            clear = (theme.width(_printed(plan, plan.series[series][1][category])) + s.gap_s if outside
                     else 0) + s.bar_pad_y
            words = Rect(frame.right + s.gap_s, round(y - line / 2), width, line)
            start, end = round(x + clear), words.left - s.bar_pad_y
            ruler = Rect(start, round(y - s.hairline / 2), end - start, s.hairline) if end > start else None
        else:
            x = inner.left + along(category, series, inner.width)
            y = inner.bottom - toward(tip, inner.height)
            clear = (line if outside else 0) + s.bar_pad_y
            words = Rect(min(max(round(x - width / 2), rect.left), max(rect.right - width, rect.left)),
                         rect.top, width, line)
            start, end = words.bottom, round(y - clear)
            ruler = Rect(round(x - s.hairline / 2), start, s.hairline, end - start) if end > start else None
        if not rect.contains(words):
            raise PageFullError(f"{what}: the callout {text!r} does not fit beside the chart — fewer words")
        placed.append(Callout(text, words, ruler))

    for index, one in enumerate(placed):
        for other in placed[index + 1:]:
            apart = Rect(one.words.left - s.gap_s // 2, one.words.top, one.words.width + s.gap_s, one.words.height)
            if apart.overlaps(other.words):
                raise PageFullError(
                    f"{what}: the callouts {one.text!r} and {other.text!r} would print over each other — "
                    "fewer words, or one callout fewer; they are not moved apart")

    fractions = ((inner.left - frame.left) / frame.width, (inner.top - frame.top) / frame.height,
                 inner.width / frame.width, inner.height / frame.height)
    return frame, Pinned(fractions, low, high, step, GAP), tuple(placed)
