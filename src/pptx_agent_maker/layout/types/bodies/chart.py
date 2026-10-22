"""A chart drawn from its numbers, which a person can still edit in PowerPoint: `chart`.

**伝えたいことが図を決める。**比べるなら棒、移り変わりなら折れ線、内訳なら積み上げ、増減の積み重ねなら
滝グラフ、2 つの量の関係なら点 (= 散布図)、区分ごとの分布を 1 件ずつ見せるなら点の列 (= `strip`) ― 7 つで
足りる。絵で貼ったグラフは、数字が 1 つ変わるたびに描き直しになり、渡した先では誰も直せない。ここで書くグラフは
数字を deck の中に持ち、PowerPoint の「データの編集」で直せる。

見た目は決まっている (= 頁が選べるのは、どの 1 つを目立たせるかだけ):

* **目を集めるのは 1 つ。**`highlight` に書いた系列か項目だけが差し色で、ほかは灰
* **値の数字は棒に付ける。**目盛りの線は引かず、数字を付けたグラフは値の軸も出さない
  (= 同じ数を 2 度見せない)。`labels = false` なら数字を付けず、値の軸が出る
* **値の軸を隠したグラフは、0 から立つ** (= 棒の高さが値の比になる。近い値ばかりのグラフで、描く側の自動が
  下限を 0 より上に取り、軸が見えないまま棒の比が値の比と食い違った)
* **値の軸の範囲を書いたグラフ (= `scale`) だけは、値の軸と目盛りの線を出す** (= 数字は棒に付けたまま)。
  5 段階の評価のように、読み手が「どの範囲のどこか」を目で測るグラフ。下限が 0 でない時は棒が途中から立つので、
  それが分かるよう軸は必ず出る
* **凡例は系列が 2 つ以上の時だけ**
* 字の大きさは本文の大きさ、書体は頁と同じ

数は manifest に書くか、素材の folder の CSV から読む (= `data = "x.csv"`。1 列目が項目、2 列目からが
系列、1 行目が系列の名前)。

小さな棒だけを並べる図 (= `bare`) は数字も値の軸も出さず、棒と項目の名前だけを描く。横棒は、項目の名前の下に
1 行の説明 (= `notes`) を添えられる。

点のグラフ (= `scatter`) だけは数の形が違う ― 項目を持たず、系列は点 (= x と y の 1 組) の集まり。軸が何かを
言わない散布図は読めないので、軸の名前 (= `x` と `y`) を必ず書く。CSV は 1 列目が x、2 列目からが系列の y。

グラフの 1 点を指す注記は `callouts` に、**どの項目のどの系列か**で書く (= 座標は書かない)。点の位置は
道具が計算し、言葉をグラフの外 (= 縦のグラフは上、横棒は右) に、細い線を点まで置く。そのために、
注記を持つグラフだけは、描く範囲と値の軸を道具が決めて書き出す。

散布図の点は名前を持てる (= `[x, y, "名前"]`。点の横に名前と数字が出る) し、`grid` で薄い格子を引ける。点の列
(= `strip`) は行ごとに点を並べる ― 横は対数の軸、行の名前は左、説明 (= `notes`) は右。名前の付いた散布図と点の列は、
言葉を点に合わせて置くために、描く範囲と軸を道具が決めて書き出す。

⚠ **組み合わせのグラフ (= 棒と折れ線) は無い。**書き出す口が無く、2 つの読みを 1 枚に載せることにもなる。
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

from ...base.geometry import Rect, pt
from ...parts.elements import Callout, Chart, Label, Pinned, Plane, Series
from ...parts.look import TONES
from ...parts.page import Page, PageFullError
from ..core.read import Spec, only_keys, read_tone
from ..core.registry import PageTypeError, register

#: グラフの種類。`bar` は横棒、`column` は縦棒、`stacked` は積み上げた縦棒、`waterfall` は滝グラフ、
#: `scatter` は点 (= 2 つの量の関係)、`strip` は行ごとの点の列 (= 1 件 1 点を、対数の軸に並べる)
KINDS = ("bar", "column", "line", "stacked", "waterfall", "scatter", "strip")
#: グラフが読むキー
KEYS = ("kind", "categories", "series", "data", "highlight", "highlight_tone", "unit", "labels", "totals", "callouts", "x", "y",
        "scale", "bare", "notes")
#: 数字も値の軸も持たない小さな棒 (= `bare`) が書ける種類
BARE = ("bar", "column")
#: `bare` と一緒に書けないキー (= 数字と値の軸に付くもの、どちらも `bare` は出さない)
BARE_NOT = ("labels", "unit", "scale", "callouts")
#: 値の軸の範囲が読むキー (= 下限・上限・目盛りの間)
SCALE_KEYS = ("from", "to", "step")
#: 目盛りの数の上限 (= これより細かい目盛りの線は、地の模様になって読めない)
MOST_TICKS = 20
#: 点のグラフが読むキー (= 項目も、棒に付ける数字も、柱を指す注記も持たない)
POINT_KEYS = ("kind", "x", "y", "series", "data", "highlight", "highlight_tone", "grid")
#: 点の印の大きさ (pt)。点の横の言葉を置く場所は、この大きさから計算する (= 書き出す側の既定と同じ)
MARK = 7
#: 点のグラフの系列が読むキー
POINT_SERIES_KEYS = ("name", "points", "tone")
#: 点の列 (= `strip`) が読むキー。行 = 項目、1 件 = 点 1 つ
STRIP_KEYS = ("kind", "categories", "series", "notes", "axis", "ticks", "median", "highlight", "highlight_tone", "legend")
#: 点の列の系列が読むキー (= `values` は項目ごとの、点の値の並び)
STRIP_SERIES_KEYS = ("name", "values", "tone")
#: 点の列の、行ごとの中央値を描く系列の名前 (= PowerPoint の表にも、この名前の列が並ぶ)
MEDIAN = "Median"
#: 点の列の印の大きさ (pt)。点どうしを重ねないための、縦のずらし幅もこれから出す
STRIP_MARK = 6
#: 中央値の輪が、点より大きい分 (pt)。奇数個の行の中央値は、ある点と同じ位置に立つ ― 同じ大きさでは点に隠れる
RING_OVER = 3
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
    #: 値の軸の (下限, 上限, 目盛りの間)。書かなければ None (= 軸は PowerPoint が決める)
    scale: tuple[float, float, float] | None = None
    #: 数字も値の軸も出さない (= 棒と、下の項目の名前だけ)
    bare: bool = False
    #: 横棒の、項目ごとの 1 行の説明 (= 名前の下に置く。言葉の無い項目は空)
    notes: tuple[str, ...] = ()
    #: `highlight` の 1 つを塗る色の役 (= 書かなければ空で、差し色)
    highlight_tone: str = ""

    @property
    def axis(self) -> bool:
        """Whether the value axis is drawn: the bars carry their numbers, so it is hidden unless it says a range."""
        return not self.bare and (not self.labels or self.scale is not None)


@register("chart", needs=["chart"])
def _chart(page: Page, spec: Spec, area: Rect) -> None:
    """One chart holding the body."""
    place_chart(page, spec, spec.get("chart"), area, "chart")


def place_chart(page: Page, spec: Spec, written, rect: Rect, what: str) -> None:
    """Read a chart as written and put it in `rect` (= as a page's body, or in a cell of a compose)."""
    theme, palette = page.theme, page.theme.palette
    # どのグラフも同じ: 字は本文の大きさと色、軸の線は区切りの線の色
    look = dict(size=theme.type.body, colour=palette.ink, line=palette.rule)
    if isinstance(written, dict) and written.get("kind") == "strip":
        _strip(page, spec, written, rect, what, look)
        return
    if isinstance(written, dict) and written.get("kind") == "scatter":
        points = _points(page, spec, written, what)
        series = points.series
        plane = _plane(page, rect, points, what) if points.named else None
        if plane:
            series = _labelled(series, points, plane, page, rect, what)
        page.chart(Chart("chart", rect, "scatter", (), series, legend=len(series) > 1, axis=True,
                         x_title=points.titles[0], y_title=points.titles[1],
                         grid=page.theme.palette.rule if points.grid else "", plane=plane, **look))
        return
    plan = _read(spec, written, what)
    series, legend = (_waterfall(page, plan, what) if plan.kind == "waterfall" else _plain(page, plan, what))
    _readable(page, plan, rect, legend, what)
    frame, pinned, callouts = (_pointed(page, plan, rect, legend, what) if plan.callouts or plan.notes
                               else (None, None, ()))
    page.chart(Chart(
        "chart", rect, "stacked" if plan.kind == "waterfall" else plan.kind, plan.categories, series,
        legend=legend, axis=plan.axis, frame=frame, pinned=pinned,
        callouts=callouts, scale=plan.scale, **look))


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
    bare = _bare(written, kind, what)
    totals = written.get("totals", [])
    if kind != "waterfall" and "totals" in written:
        raise PageTypeError(f"{what}: `totals` belongs to a waterfall, and this is a {kind}")
    if not isinstance(totals, list) or any(str(name) not in categories for name in totals):
        raise PageTypeError(f"{what}: `totals` lists the categories that are totals (= bars that stand on "
                            f"the ground), each by its name; the categories are {', '.join(categories)}")
    callouts = _callouts(written.get("callouts"), kind, categories, names, what)
    notes = _notes(written.get("notes"), kind, categories, what)
    plan = _Plan(kind, tuple(categories), tuple(series), highlight, unit, labels and not bare,
                 tuple(str(name) for name in totals), callouts, bare=bare, notes=notes,
                 highlight_tone=_highlight_tone(spec, written, highlight, what))
    if "scale" not in written:
        return plan
    return replace(plan, scale=_scale(written["scale"], plan, what))


def _bare(written: dict, kind: str, what: str) -> bool:
    """Whether the chart is a small one of bars alone: no numbers on them and no value axis.

    ⚠ **数字も軸も出さない棒は、0 から立つ** (= 値の軸を隠したグラフと同じ)。棒どうしの高さの比が値の比で、
    読み手は大きさを比べるだけ。数字や範囲を言うキーと一緒には書けない (= 言うことが食い違う)。
    """
    bare = written.get("bare", False)
    if not isinstance(bare, bool):
        raise PageTypeError(f"{what}: `bare` is true or false, not {bare!r}")
    if not bare:
        return False
    if kind not in BARE:
        raise PageTypeError(f"{what}: `bare` is a small chart of bars alone ({', '.join(BARE)}), and this is a {kind}")
    said = [key for key in BARE_NOT if key in written]
    if said:
        raise PageTypeError(f"{what}: `bare` shows no numbers and no value axis, and {', '.join(f'`{k}`' for k in said)} "
                            "speaks of them — take one or the other off")
    return True


def _scale(written, plan: _Plan, what: str) -> tuple[float, float, float]:
    """The value axis as written: where it starts and ends, and the step of its ticks.

    ⚠ **範囲の外の値は止める。**軸の外へ出た棒は枠で切れ、切れたことは絵から分からない。
    ⚠ **積み上げは 0 から**、**滝グラフと注記付きのグラフは書けない** ― 積み上げは下の段が 0 から立つ前提で
    読まれ、滝グラフは見えない土台の上に立ち、注記付きのグラフは言葉を点に合わせるために軸を自分で決める。
    """
    where = f"{what}: `scale`"
    if not isinstance(written, dict):
        raise PageTypeError(f"{where} is {{ from = …, to = …, step = … }} (= where the value axis starts and "
                            f"ends, and the step of its ticks), not {written!r}")
    only_keys(written, set(SCALE_KEYS), where)
    missing = [key for key in SCALE_KEYS if key not in written]
    if missing:
        raise PageTypeError(f"{where} needs {', '.join(f'`{key}`' for key in missing)} — "
                            "{ from = 1, to = 5, step = 1 } is a scale of five")
    low, high, step = (_number(written[key], f"{where} `{key}`") for key in SCALE_KEYS)
    if plan.kind == "waterfall":
        raise PageTypeError(f"{where}: a waterfall stands on bars that are not drawn, and the axis follows them — "
                            "it takes no scale")
    if plan.callouts:
        raise PageTypeError(f"{where}: a chart with callouts works out its own axis to put the words over the "
                            "points — take the callouts or the scale off")
    if plan.notes:
        raise PageTypeError(f"{where}: a chart with notes works out its own axis to put the notes beside the "
                            "bars — take the notes or the scale off")
    if not low < high:
        raise PageTypeError(f"{where}: `from` ({low}) is below `to` ({high})")
    ticks = (high - low) / step if step > 0 else 0
    if step <= 0 or abs(ticks - round(ticks)) > 1e-9 or round(ticks) > MOST_TICKS:
        raise PageTypeError(f"{where}: `step` ({step}) divides {low} to {high} into whole steps, "
                            f"at most {MOST_TICKS} of them")
    if plan.kind == "stacked" and low > 0:
        raise PageTypeError(f"{where}: a stacked column is read from 0 — its lowest part would be cut off at {low}")
    if plan.kind == "stacked":
        reach = [(sum(min(values[i], 0) for _n, values, _t in plan.series),
                  sum(max(values[i], 0) for _n, values, _t in plan.series)) for i in range(len(plan.categories))]
        outside = [plan.categories[i] for i, (down, up) in enumerate(reach) if down < low or up > high]
    else:
        outside = [f"{plan.categories[i]} ({name})" if len(plan.series) > 1 else plan.categories[i]
                   for name, values, _tone in plan.series for i, value in enumerate(values)
                   if not low <= value <= high]
    if outside:
        raise PageTypeError(f"{where}: {', '.join(outside)} fall outside {low} to {high} — a bar past the axis "
                            "is cut off where it ends, and nothing shows it was")
    return low, high, step


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


def _notes(listed, kind: str, categories: list[str], what: str) -> tuple[str, ...]:
    """The notes as written: one line of words for each category (= under a bar's name, or beside a strip's row)."""
    if listed is None:
        return ()
    if kind not in ("bar", "strip"):
        raise PageTypeError(f"{what}: `notes` are set under the names of a bar chart's categories (or beside the "
                            f"rows of a strip), and this is a {kind} — its names run along the bottom")
    if (not isinstance(listed, list) or len(listed) != len(categories)
            or any(not isinstance(note, str) or "\n" in note for note in listed)):
        raise PageTypeError(f"{what}: `notes` is one line of words for each of the {len(categories)} categories "
                            "(= \"\" for one with nothing to add)")
    return tuple(note.strip() for note in listed)


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


@dataclass(frozen=True)
class _Points:
    """What a scatter wrote, checked."""

    #: 横の軸と縦の軸の名前
    titles: tuple[str, str]
    #: 描く形の系列 (= 色まで決まっている。点の名前の字はまだ無い)
    series: tuple[Series, ...]
    #: 系列ごとの、点の名前 (= 付けない点は空)
    names: tuple[tuple[str, ...], ...]
    grid: bool

    @property
    def named(self) -> bool:
        return any(name for names in self.names for name in names)


def _points(page: Page, spec: Spec, written: dict, what: str) -> _Points:
    """A scatter as written, checked: the names of its two axes, the series as they are drawn, and each point's name."""
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
    grid = written.get("grid", False)
    if not isinstance(grid, bool):
        raise PageTypeError(f"{what}: `grid` is true or false, not {grid!r}")
    if "data" in written:
        if "series" in written:
            raise PageTypeError(f"{what}: the numbers come from `data` or from `series`, not from both")
        series = _points_from_file(spec, written["data"], what)
    else:
        series = _points_written(spec, written, what)
    names = [name for name, _points_, _tone, _named in series]
    if len(set(names)) != len(names):
        raise PageTypeError(f"{what}: a series is written twice — each has a name of its own")
    highlight = written.get("highlight", "")
    if not isinstance(highlight, str) or (highlight and highlight not in names):
        raise PageTypeError(f"{what}: `highlight` is {highlight!r}, which is not one of the series "
                            f"({', '.join(names)})")
    toned = [name for name, _points_, tone, _named in series if tone]
    if highlight and toned:
        raise PageTypeError(f"{what}: `highlight` already says which one stands out — "
                            f"take the `tone` off {', '.join(toned)}")
    standing = _highlight_tone(spec, written, highlight, what)
    drawn = []
    for index, (name, points, tone, _named) in enumerate(series):
        colour, _edge = _series_colour(page, index, name, tone, (name == highlight) if highlight else None, what,
                                       standing)
        drawn.append(Series(name, tuple(y for _x, y in points), colour, xs=tuple(x for x, _y in points)))
    return _Points((titles[0], titles[1]), tuple(drawn), tuple(named for _n, _p, _t, named in series), grid)


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
                or any(not isinstance(point, list) or len(point) not in (2, 3) for point in points)):
            raise PageTypeError(f"{where} ({name}): `points` is a list of [x, y] or [x, y, \"its name\"], at least one")
        named = []
        for index, point in enumerate(points, start=1):
            label = point[2] if len(point) == 3 else ""
            if len(point) == 3 and (not isinstance(label, str) or not label.strip() or "\n" in label):
                raise PageTypeError(f"{where} ({name}), `points` {index}: the name of a point is a few words on "
                                    f"one line, not {label!r} (= leave it out for a point with no name)")
            named.append(label.strip())
        tone = read_tone(spec, item, where, "") if "tone" in item else ""
        series.append((name, tuple(
            (_number(point[0], f"{where} ({name}), `points` {index}, x"),
             _number(point[1], f"{where} ({name}), `points` {index}, y"))
            for index, point in enumerate(points, start=1)), tone, tuple(named)))
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
    return [(series, tuple(found), "", ("",) * len(found)) for series, found in zip(names, points)]


#: 名前を付けた点のグラフが、軸の端に取る余白 (= 点の範囲に対する割合。端の点の言葉が軸の外へ出ないように)
ROOM = 0.08


def _axis_of(values: list[float]) -> tuple[float, float, float]:
    """Where an axis runs from and to, and the step of its ticks: the numbers with a little room round them."""
    low, high = min(values), max(values)
    span = (high - low) or abs(high) or 1.0
    low, high = low - span * ROOM, high + span * ROOM
    step = _nice(high - low)
    return (round(math.floor(round(low / step, 9)) * step, 10), round(math.ceil(round(high / step, 9)) * step, 10),
            step)


def _plane(page: Page, rect: Rect, points: _Points, what: str) -> Plane:
    """Where the plot of a scatter with named points is held, and what both axes run over.

    点の横に言葉を置くには、点の位置を知る必要がある ― 描く範囲と軸を道具が決めて書き出す (= 注記と同じ)。
    描く範囲の外 (= 軸の名前と数字、凡例) の場所は、ここで除く。
    """
    theme, s = page.theme, page.theme.spacing
    line, pad = theme.line_height(), s.gap_s
    x_axis = _axis_of([x for series in points.series for x in series.xs])
    y_axis = _axis_of([y for series in points.series for y in series.values])
    ticks = [y_axis[0] + y_axis[2] * index for index in range(round((y_axis[1] - y_axis[0]) / y_axis[2]) + 1)]
    below = line + pad if len(points.series) > 1 else 0
    left = rect.left + pad + line + pad + max(theme.width(f"{tick:g}") for tick in ticks) + pad
    top, right = rect.top + max(pad, line // 2), rect.right - pad
    bottom = rect.bottom - below - 2 * (line + pad) - pad
    if right - left <= 0 or bottom - top <= 0:
        raise PageFullError(f"{what}: the chart has no room left for its plot beside its axes and its names — "
                            "give it more room")
    return Plane(((left - rect.left) / rect.width, (top - rect.top) / rect.height,
                  (right - left) / rect.width, (bottom - top) / rect.height), x_axis, y_axis)


def _labelled(series: tuple[Series, ...], points: _Points, plane: Plane, page: Page, rect: Rect,
              what: str) -> tuple[Series, ...]:
    """Each named point gets its name and its numbers beside it: to the right, or to the left at the chart's edge.

    **言葉どうしが重なるなら止まる** (= 縮めない、ずらさない)。言葉の場所は点の位置から計算し、軸の端と
    描く範囲は上の `_plane` が決めたもの。
    """
    theme, s = page.theme, page.theme.spacing
    small = theme.type.caption                         # 点の名前は、本文より小さな字
    line = theme.line_height(small)
    fx, fy, fw, fh = plane.inner
    inner = Rect(round(rect.left + fx * rect.width), round(rect.top + fy * rect.height),
                 round(fw * rect.width), round(fh * rect.height))
    (x_low, x_high, _), (y_low, y_high, _) = plane.x, plane.y
    reach = s.bar_pad_y + pt(MARK) // 2                # 点の真ん中から、言葉までの間
    places = (_places(x for one in series for x in one.xs), _places(y for one in series for y in one.values))
    placed, found = [], []
    for one, names in zip(series, points.names):
        labels = []
        for index, (name, x, y) in enumerate(zip(names, one.xs, one.values)):
            if not name:
                continue
            text = f"{name}\n({x:,.{places[0]}f}, {y:,.{places[1]}f})"
            wide, tall = max(theme.width(part, small) for part in text.split("\n")), 2 * line
            middle_x = inner.left + inner.width * (x - x_low) / (x_high - x_low)
            middle_y = inner.bottom - inner.height * (y - y_low) / (y_high - y_low)
            right = Rect(round(middle_x + reach), round(middle_y - tall / 2), wide, tall)
            left = Rect(round(middle_x - reach - wide), right.top, wide, tall)
            for words, toward_left in ((right, False), (left, True)):
                if rect.contains(words):
                    break
            else:
                raise PageFullError(f"{what}: the words of {name!r} do not fit beside its point — fewer words, "
                                    "or more room")
            placed.append((name, words))
            labels.append(Label(index, text, toward_left, small))
        found.append(replace(one, labels=tuple(labels), mark=MARK))
    for number, (name, words) in enumerate(placed):
        for other, there in placed[number + 1:]:
            apart = Rect(words.left - s.gap_s // 2, words.top, words.width + s.gap_s, words.height)
            if apart.overlaps(there):
                raise PageFullError(
                    f"{what}: the words of {name!r} and {other!r} would print over each other — "
                    "fewer points named; they are not moved apart")
    return tuple(found)


# -- a strip of points -----------------------------------------------------------


@dataclass(frozen=True)
class _Strip:
    """What a strip wrote, checked."""

    rows: tuple[str, ...]
    notes: tuple[str, ...]
    #: 横の軸の目盛り (= 10 の累乗を、小さい方から)
    ticks: tuple[float, ...]
    #: (系列の名前, 書かれた色の役, 項目ごとの点の値)
    series: tuple[tuple[str, str, tuple[tuple[float, ...], ...]], ...]
    highlight: str
    median: bool
    legend: bool | None
    #: `highlight` の 1 つを塗る色の役 (= 書かなければ空で、差し色)
    highlight_tone: str = ""


def _strip_read(spec: Spec, written: dict, what: str) -> _Strip:
    unknown = sorted(set(written) - set(STRIP_KEYS))
    if unknown:
        raise PageTypeError(f"{what}: a strip does not take {', '.join(unknown)} (= it takes "
                            f"{', '.join(STRIP_KEYS)}) — it has no numbers beside the points and no callouts")
    if written.get("axis") != "log":
        raise PageTypeError(f"{what}: a strip says what its axis is — `axis = \"log\"` (= a tick at every power "
                            f"of ten), not {written.get('axis')!r}")
    rows = written.get("categories")
    if (not isinstance(rows, list) or not rows or any(not isinstance(row, str) or not row.strip() for row in rows)):
        raise PageTypeError(f"{what}: `categories` is the list of rows, each with its name (= a few lines, "
                            "joined by \\n)")
    rows = [row.strip() for row in rows]
    if len(set(rows)) != len(rows):
        raise PageTypeError(f"{what}: a row is written twice — each has a name of its own")
    notes = _notes(written.get("notes"), "strip", rows, what)
    ticks = _ticks(written.get("ticks"), what)
    listed = written.get("series")
    if not isinstance(listed, list) or not listed:
        raise PageTypeError(f"{what}: `series` is a list of {{ name = …, values = [[…], …] }}, at least one — "
                            "`values` is the list of points of each row, in the order of `categories`")
    series = []
    for number, item in enumerate(listed, start=1):
        where = f"{what}: series {number}"
        only_keys(item, set(STRIP_SERIES_KEYS), where)
        name = str(item.get("name", "")).strip()
        if not name:
            raise PageTypeError(f"{where} has no `name` — it heads the column of numbers a person edits")
        values = item.get("values")
        if not isinstance(values, list) or len(values) != len(rows) or any(not isinstance(row, list) for row in values):
            raise PageTypeError(f"{where} ({name}): `values` is one list of numbers for each of the {len(rows)} "
                                "rows (= [] for a row with no point)")
        for row, found in zip(rows, values):
            for value in found:
                _number(value, f"{where} ({name}), row {row!r}")
                if not ticks[0] <= value <= ticks[-1]:
                    raise PageTypeError(f"{where} ({name}), row {row!r}: {value:g} falls outside the axis, "
                                        f"{ticks[0]:g} to {ticks[-1]:g} — a point past the axis is cut off")
        if not any(values):
            raise PageTypeError(f"{where} ({name}) has no point at all")
        tone = read_tone(spec, item, where, "") if "tone" in item else ""
        series.append((name, tone, tuple(tuple(found) for found in values)))
    names = [name for name, _tone, _values in series]
    if len(set(names)) != len(names) or MEDIAN in names:
        raise PageTypeError(f"{what}: a series is written twice — each has a name of its own"
                            + (f" (and {MEDIAN!r} is the name of the medians)" if MEDIAN in names else ""))
    highlight = written.get("highlight", "")
    if not isinstance(highlight, str) or (highlight and highlight not in names):
        raise PageTypeError(f"{what}: `highlight` is {highlight!r}, which is not one of the series "
                            f"({', '.join(names)})")
    toned = [name for name, tone, _values in series if tone]
    if highlight and toned:
        raise PageTypeError(f"{what}: `highlight` already says which one stands out — "
                            f"take the `tone` off {', '.join(toned)}")
    flags = {}
    for key in ("median", "legend"):
        if key in written and not isinstance(written[key], bool):
            raise PageTypeError(f"{what}: `{key}` is true or false, not {written[key]!r}")
        flags[key] = written.get(key)
    return _Strip(tuple(rows), notes, ticks, tuple(series), highlight, bool(flags["median"]), flags["legend"],
                  _highlight_tone(spec, written, highlight, what))


def _ticks(written, what: str) -> tuple[float, ...]:
    """The ticks of a log axis: every power of ten from the first to the last, which are the ends of the axis.

    ⚠ **対数の軸が目盛りを打てるのは 10 の累乗だけ** (= PowerPoint の対数の軸は、底の累乗ごとに線を引く)。
    1・3・10 のような目盛りは書けない。
    """
    if not isinstance(written, list) or len(written) < 2:
        raise PageTypeError(f"{what}: `ticks` is the powers of ten the axis marks, from the smallest to the largest — "
                            "[1, 10, 100], as many as it needs")
    ticks = [_number(tick, f"{what}: `ticks`") for tick in written]
    powers = [round(math.log10(tick)) if tick > 0 else None for tick in ticks]
    if (any(power is None or abs(10.0 ** power - tick) > 1e-9 * tick for power, tick in zip(powers, ticks))
            or any(after - before != 1 for before, after in zip(powers, powers[1:]))):
        raise PageTypeError(f"{what}: `ticks` is every power of ten from the smallest to the largest "
                            f"(= [1, 10, 100]), not {written!r} — a log axis marks no other number")
    return tuple(ticks)


def _middle(values: list[float]) -> float:
    """The median: the middle number, or the mean of the two in the middle."""
    ordered = sorted(values)
    half = len(ordered) // 2
    return ordered[half] if len(ordered) % 2 else (ordered[half - 1] + ordered[half]) / 2


def _swarm(across: list[float], size: float, reach: float) -> list[float]:
    """How far each mark of one row stands off the row's middle (= down is plus), so no two marks cover each other.

    `across` は点の横の位置 (EMU)、`size` は印の直径、`reach` は行の中央から離れてよい上限。左から順に、中央から
    近い順 (= 0、下、上、2 つ下 …) に、すでに置いた印と触れない最初の位置へ。どこにも置けなければ、
    いちばん離れられる位置 (= 重なりは、行が低すぎる印)。同じ入力は同じ答えになる。
    """
    steps = max(int(reach // size), 0)
    candidates = [0.0] + [sign * size * k for k in range(1, steps + 1) for sign in (1, -1)]
    placed: list[tuple[float, float]] = []
    offsets = [0.0] * len(across)
    for index in sorted(range(len(across)), key=lambda i: (across[i], i)):
        x = across[index]

        def clearance(offset: float) -> float:
            return min((math.hypot(x - other_x, offset - other) for other_x, other in placed), default=size)

        offset = next((offset for offset in candidates if clearance(offset) >= size),
                      max(candidates, key=clearance))
        placed.append((x, offset))
        offsets[index] = offset
    return offsets


def _strip(page: Page, spec: Spec, written: dict, rect: Rect, what: str, look: dict) -> None:
    """A strip: a row for each category, a mark for each number on a log axis, the median of a row ringed.

    行の名前は点の列の左、`notes` は右に置く (= 言葉の場所は、描く範囲を道具が決めるので計算できる)。
    **1 件 = 点 1 つ**で、近い点が覆い合わないよう、行の中で縦にずらす ― ずらした高さは行の番号に足した
    数なので、PowerPoint の表の「縦」の列は、行の番号と小さなずれの和。
    """
    plan = _strip_read(spec, written, what)
    theme, palette, s = page.theme, page.theme.palette, page.theme.spacing
    line, pad, small = theme.line_height(), s.gap_s, theme.type.caption
    count = len(plan.rows)
    legend = plan.legend if plan.legend is not None else len(plan.series) + plan.median > 1

    # 1. 描く範囲 ― 左に行の名前、右に説明、上に軸の字 (= 縦の軸が上から数えるので、横の軸は上に出る)、下に凡例
    names = [row.split("\n") for row in plan.rows]
    lead = max(theme.width(part) for parts in names for part in parts)
    trail = max((theme.width(note, small) for note in plan.notes), default=0)
    left = rect.left + lead + pad
    right = rect.right - ((trail + pad) if trail else pad)
    top = rect.top + line + pad
    bottom = rect.bottom - ((line + pad) if legend else 0) - pad
    if right - left <= 0 or bottom - top <= 0:
        raise PageFullError(f"{what}: the strip has no room left for its plot beside the names of its rows — "
                            "give it more room, or say less")
    slot = (bottom - top) / count
    tallest = max(len(parts) for parts in names) * line
    if slot < tallest:
        raise PageFullError(f"{what}: each of the {count} rows has {slot / pt(1):.0f} pt, and the name of the tallest "
                            f"needs {tallest / pt(1):.0f} — more room, fewer rows, or fewer lines in a name")
    inner = Rect(left, top, right - left, bottom - top)

    # 2. 点 ― 横は値 (= 対数の軸の上の位置)、縦は行の番号に、覆い合わないためのずれを足した数
    span = math.log10(plan.ticks[-1]) - math.log10(plan.ticks[0])
    mark = pt(STRIP_MARK)

    def across(value: float) -> float:
        return inner.width * (math.log10(value) - math.log10(plan.ticks[0])) / span

    columns: list[list[float]] = [[] for _ in plan.series]
    xs: list[list[float]] = [[] for _ in plan.series]
    middles: list[tuple[float, float]] = []
    for row in range(count):
        found = [(value, index) for index, (_name, _tone, values) in enumerate(plan.series) for value in values[row]]
        offsets = _swarm([across(value) for value, _index in found], mark, slot / 2 - mark / 2)
        for (value, index), offset in zip(found, offsets):
            xs[index].append(value)
            columns[index].append(row + 1 + offset / slot)
        if found:
            middles.append((_middle([value for value, _index in found]), row + 1))

    highlight = plan.highlight
    drawn = []
    for index, (name, tone, _values) in enumerate(plan.series):
        colour, _edge = _series_colour(page, index, name, tone, (name == highlight) if highlight else None, what,
                                       plan.highlight_tone)
        drawn.append(Series(name, tuple(columns[index]), colour, xs=tuple(xs[index]), mark=STRIP_MARK))
    if plan.median:
        # 白抜き (= 塗らず、縁だけ)。ほかの点の上に重なっても、下の点が輪の中に見える
        drawn.append(Series(MEDIAN, tuple(row for _value, row in middles), "",
                            xs=tuple(value for value, _row in middles), outline=palette.ink, mark=STRIP_MARK + RING_OVER))

    # 3. 行の名前 (= 左) と説明 (= 右)。行の真ん中に、中央揃え (= 縦) で
    words = []
    for row, parts in enumerate(names):
        middle = top + slot * (row + 0.5)
        height = len(parts) * line
        words.append(Callout("\n".join(parts), Rect(rect.left, round(middle - height / 2), lead, height), align="left"))
        if plan.notes[row] if plan.notes else False:
            words.append(Callout(plan.notes[row], Rect(right + pad, round(middle - theme.line_height(small) / 2), trail,
                                                       theme.line_height(small)),
                                 align="left", size=small, colour=palette.muted))

    plane = Plane(((left - rect.left) / rect.width, (top - rect.top) / rect.height,
                   inner.width / rect.width, inner.height / rect.height),
                  (plan.ticks[0], plan.ticks[-1], 10), (0.5, count + 0.5, 1), log=True, down=True,
                  x_format="#,##0" if plan.ticks[0] >= 1 else "General")
    page.chart(Chart("chart", rect, "scatter", (), tuple(drawn), legend=legend, axis=False, grid=palette.rule,
                     plane=plane, callouts=tuple(words), **look))


# -- drawing ---------------------------------------------------------------------


def _series_colour(page: Page, index: int, name: str, tone: str, standing_out: bool | None,
                   what: str, standing_tone: str = "") -> tuple[str, str]:
    """(the colour, the edge) of one series, by the rule every chart shares.

    `standing_out` は、グラフが `highlight` を持つ時だけ言う (= この系列がその 1 つか)。その 1 つは
    `standing_tone` の色 (= `highlight_tone`、書かなければ差し色)。持たなければ、書いた `tone`、書かなければ
    順番で決まる色 (= 最初が主役、続きは灰の濃淡)。
    """
    palette = page.theme.palette
    if standing_out is not None:
        return (_standing_colour(page, standing_tone) if standing_out else palette.muted), ""
    if tone:
        # 薄い地の系列は、箱と同じく地を濃くした色の枠を持つ (= 紙の上で棒の端が読める)
        colour, _words, edge = page.ground(tone)
        return colour, edge
    if index < len(UNSAID):
        return getattr(palette, UNSAID[index]), ""
    raise PageTypeError(
        f"{what}: series {index + 1} ({name}) has no colour of its own — past the first "
        f"{len(UNSAID)}, give each series a `tone` ({', '.join(TONES)}), or `highlight` one")


def _highlight_tone(spec: Spec, written: dict, highlight: str, what: str) -> str:
    """The tone the one `highlight` names is painted in (= `highlight_tone`, the agenda's word), or empty for the accent.

    書けるのは目次の `highlight_tone` と同じ (= 道具の色の役と、案件が `[theme.grounds]` で名前を付けた地)。
    """
    if "highlight_tone" not in written:
        return ""
    if not highlight:
        raise PageTypeError(f"{what}: `highlight_tone` is the colour of the one `highlight` names, and none is named")
    return read_tone(spec, {"tone": written["highlight_tone"]}, f"{what}: `highlight_tone`", "")


def _standing_colour(page: Page, tone: str) -> str:
    """The colour of the one that stands out: the ground of `tone`, or the accent when no tone is written."""
    return page.ground(tone)[0] if tone else page.theme.palette.accent


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
                                      (name == one_series) if plan.highlight else None, what, plan.highlight_tone)
        stacked = plan.kind == "stacked"
        drawn.append(Series(
            name, values, colour,
            points=((one_category, _standing_colour(page, plan.highlight_tone)),) if one_category is not None else (),
            number_format=number_format,
            # 段の中に置く数字は、その段の地の上で読める方の色。段の境は紙の色の細い線で切る
            label_colour=palette.words_on(colour, page.theme.type.body) if stacked else "",
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
        return {"number_format": _format(plan, sign) if plan.labels else "",
                "label_colour": palette.words_on(colour, page.theme.type.body)}

    return (
        Series("(base)", tuple(base)),
        Series(f"{name} +", tuple(up), palette.good, **labelled("+", palette.good)),
        Series(f"{name} -", tuple(down), palette.bad, **labelled("-", palette.bad)),
        Series(f"{name} =", tuple(total), palette.accent, **labelled("", palette.accent)),
    ), False


def _readable(page: Page, plan: _Plan, rect: Rect, legend: bool, what: str) -> None:
    """Stop a chart too low for its bars to be read, wherever it is placed (= a page's body or a cell inside rows).

    描く範囲は、注記の無いグラフでも同じ数え方で見積もる (= `_pointed` の 2 と同じ。凡例と、値の軸の字の行を除く)。
    横棒は項目ごとの帯が名前の 1 行より低ければ、名前どうしが重なる。縦のグラフは、棒の外に付く数字が描く範囲の
    半分を取れば、棒が数字の下に潰れる。どちらも縮めずに止まる (= 注記の在るグラフは `_pointed` が同じことを言う)。
    """
    theme, s = page.theme, page.theme.spacing
    line, pad = theme.line_height(), s.gap_s
    below = line + s.gap_s if legend else 0
    if plan.kind == "bar":
        plot = rect.height - 2 * pad - below - (0 if plan.labels else line + s.gap_s)
        slot = plot / len(plan.categories)
        if slot < line:
            raise PageFullError(f"{what}: each of the {len(plan.categories)} bars has {max(slot, 0) / pt(1):.0f} pt, "
                                f"and its name needs {line / pt(1):.0f} — more room, or fewer bars")
        return
    if plan.labels and plan.kind in ("column", "line"):
        plot = rect.height - max(pad, line // 2) - (line + s.gap_s) - below
        if plot <= 0 or (line + s.bar_pad_y) * 2 >= plot:
            raise PageFullError(f"{what}: the numbers on the bars would take half the plot — more room, or "
                                "`labels = false`")


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
    small = theme.type.caption                       # 名前の下の説明の大きさ

    # 1. 言葉の帯を除いた残りがグラフの枠
    if across:
        band = max(wide) + s.gap_s if wide else 0
        frame = Rect(rect.left, rect.top, rect.width - band, rect.height)
    else:
        band = line + s.gap_s
        frame = Rect(rect.left, rect.top + band, rect.width, rect.height - band)

    # 2. 枠の中の描く範囲 (= 軸の字と凡例の場所を除く)
    below = (line + s.gap_s if legend else 0)
    low, high = min(0.0, *(value for column in tops for _top, value in column)), \
        max(0.0, *(reach for column in tops for _top, reach in column))
    longest = max([theme.width(name) for name in plan.categories]
                  + [theme.width(note, small) for note in plan.notes], default=0)
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

    noted = _noted(page, plan, inner, small, what)

    fractions = ((inner.left - frame.left) / frame.width, (inner.top - frame.top) / frame.height,
                 inner.width / frame.width, inner.height / frame.height)
    return frame, Pinned(fractions, low, high, step, GAP), (*placed, *noted)


def _noted(page: Page, plan: _Plan, inner: Rect, small: float, what: str) -> tuple[Callout, ...]:
    """Where the one line under each name of a bar chart goes: right-aligned to the axis, below the name.

    項目の名前は PowerPoint が、各項目の帯の真ん中に右寄せで置く (= 軸の字。軸から棒の手前の余白だけ離れる)。
    説明はその下の 1 行で、同じ右端に揃える。帯が名前と説明の 2 行より低ければ、次の項目の名前に乗る ― 縮めずに止まる。
    """
    if not any(plan.notes):
        return ()
    theme = page.theme
    line, height = theme.line_height(), theme.line_height(small)
    slot = inner.height / len(plan.categories)
    if slot < line + height:
        raise PageFullError(f"{what}: each of the {len(plan.categories)} bars has {slot / pt(1):.0f} pt, and its "
                            f"name and its note need {(line + height) / pt(1):.0f} — more room, fewer bars, "
                            "or no notes")
    # 箱はどれも同じ幅 (= いちばん長い説明) で、字を右へ寄せる ― 箱の左端も右端も揃う
    # (= 字の幅ちょうどの箱は、左端が数 mm ずつずれて「揃っていない」と検査に言われる)
    width = max(theme.width(note, small) for note in plan.notes)
    return tuple(
        Callout(note, Rect(round(inner.left - theme.spacing.bar_pad_y - width),
                           round(inner.top + slot * (index + 0.5) + line / 2), width, height),
                align="right", size=small, colour=theme.palette.muted)
        for index, note in enumerate(plan.notes) if note)
