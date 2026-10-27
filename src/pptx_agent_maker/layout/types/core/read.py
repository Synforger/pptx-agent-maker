"""Reading what a page wrote: the declaration itself, and the tables every type reads the same way.

カード・ノード・棒・段が書ける見た目のキー (= `LOOK_KEYS`) も、色の役の読み方も、ここの 1 か所が持つ。
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Callable

from ...tokens import DEFAULT, PAPER, Band, Palette, Theme
from ...parts.elements import Mark, Shade
from ...parts.look import Style, TONES
from ...parts.page import CARD_ALIGNS, Card, Panel
from .registry import PageTypeError


@dataclass(frozen=True)
class Spec:
    """One declared page, plus the two things it needs from outside.

    `asset` と `aspect` を渡してもらうのは、頁の層が外の path も画像の中身も
    知らないまま保つため (= 座標が在るのはこの層だけ、という境界と同じ理由)。
    """

    data: dict
    asset: Callable[[str], Path]
    aspect: Callable[[Path], float]
    #: 頁の見た目 (= 案件が名前を付けた地を、`tone` として読むため)
    theme: Theme = DEFAULT

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def text(self, key: str, default: str = "") -> str:
        value = self.data.get(key, default)
        return "" if value is None else str(value)

    def figure(self, key: str = "figure") -> tuple[Path, float]:
        """An image by name, with the aspect ratio read off the file itself.

        ⚠ **縦横比を宣言に書かせない。**手で書くと、絵を差し替えた日に古い比が残って
        潰れた絵が焼ける (= 前の世代で実際に起きた)。
        """
        path = self.asset(str(self.data[key]))
        return path, self.aspect(path)

    def figures(self, key: str = "figures") -> list[tuple[Path, float, str]]:
        """Several images, each with its own caption (= `"name.png"` or `[name, caption]`)."""
        out = []
        for item in self.data[key]:
            if isinstance(item, (list, tuple)):
                name, caption = (list(item) + [""])[:2]
            else:
                name, caption = item, ""
            path = self.asset(str(name))
            out.append((path, self.aspect(path), str(caption)))
        return out

    def rows(self, key: str = "table") -> list[list[str]]:
        return read_table(self.data[key], key, self.asset)

    def cards(self) -> list[Card]:
        return [read_card(self, item, f"cards: card {number}")
                for number, item in enumerate(self.data["cards"], start=1)]


#: 表のセルに書ける状態の印。`harvey` は 4 分の幾つが済んだか (= ハーベイボール。0 は空、4 は全部)
HARVEY = "\u25cb\u25d4\u25d1\u25d5\u25cf"
#: `mark` は良い・半ば・悪い。⚠ **良いは ○ で書かない** ― ハーベイボールの「まだ何も」と同じ字になる
MARKS = {"ok": "\u2713", "partial": "\u25b3", "ng": "\u00d7"}


def read_cell(value, what: str) -> str:
    """One cell of a table: its words, or the status mark it asks for.

    地の濃さで値の大小を見せるセルは `{ text = "82%", shade = 3 }` (= 4 分の幾つか。段を決めるのは書く人)。
    印は `{ harvey = 3 }` か `{ mark = "ok" }` と書く。**印の字そのものを書かせない** ― 人ごとに
    違う字 (= ◯ と ○、✔ と ✓) が混ざり、書体によっては字形が無い。
    """
    if not isinstance(value, dict):
        return str(value)
    if set(value) == {"harvey"}:
        level = value["harvey"]
        if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level < len(HARVEY):
            raise PageTypeError(
                f"{what}: `harvey` is a whole number from 0 to {len(HARVEY) - 1} (= how many quarters "
                f"are filled), not {level!r}")
        return Mark(HARVEY[level])
    if set(value) == {"mark"}:
        if value["mark"] not in MARKS:
            raise PageTypeError(f"{what}: `mark` is one of {', '.join(MARKS)}, not {value['mark']!r}")
        return Mark(MARKS[value["mark"]])
    if set(value) == {"text", "shade"}:
        level, words = value["shade"], str(value["text"])
        if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= Palette.SHADES:
            raise PageTypeError(
                f"{what}: `shade` is a whole number from 0 to {Palette.SHADES} (= how many quarters of the "
                f"accent its ground is), not {level!r}")
        if not words.strip():
            raise PageTypeError(f"{what}: a shaded cell says its words in `text`, and this one says none")
        return Shade(words, level)
    raise PageTypeError(
        f"{what} is {value!r} — a cell is its words, one mark ({{ harvey = 0 to {len(HARVEY) - 1} }} or "
        f"{{ mark = {' | '.join(repr(name) for name in MARKS)} }}), or its words on a ground as deep as "
        f"its value ({{ text = …, shade = 0 to {Palette.SHADES} }})")


def read_band(item: dict, what: str) -> Band:
    """A row that divides a table: `{ band = "…", tone = "accent" }` (= `tone` may be left out).

    表の幅いっぱいに立つ見出しの行で、見た目 (= `table_look`) を問わず書ける。色の役か案件の地の名前かは、
    地を引ける所 (= `Page.table`) が確かめる ― ここは書き方だけ。
    """
    only_keys(item, {"band", "tone"}, what)
    words, tone = item.get("band"), item.get("tone", "")
    if not isinstance(words, (str, int, float)) or isinstance(words, bool) or not str(words).strip():
        raise PageTypeError(f"{what}: a band says its words in `band`, and this one says none")
    if not isinstance(tone, str):
        raise PageTypeError(f"{what}: `tone` is a colour's role, as in tone = \"accent\", not {tone!r}")
    return Band(str(words), tone)


#: 表を素材の CSV から読む時に書けるキー (= 素材の名前、残す列、手で足す注)
TABLE_DATA_KEYS = {"data", "columns", "cells"}
#: `cells` の 1 件が書けるキー (= どのマスか 2 つ、足す字か置き換える字か 2 つ)
TABLE_CELL_KEYS = {"row", "column", "after", "text"}


def read_table(table, what: str, asset: Callable[[str], Path]) -> list[list[str]]:
    """A table as written: rows of cells, or a CSV among the assets (= `{ data = "x.csv" }`).

    表を読む所はここ 1 か所 (= 頁の `table` も `compose` のマスの `table` も通る)。素材の探し方 `asset` は
    呼ぶ側 (= `Spec`) が渡す。
    """
    if isinstance(table, dict):
        return _read_table_file(table, what, asset)
    return _read_table_rows(table, what)


def _read_table_rows(rows, what: str) -> list[list[str]]:
    """A table written as rows of cells, each read by `read_cell`, and bands that divide it.

    ⚠ **見出しの行は、列のセルで書く。**区切りは見出しの下の行を分ける物で、その下に行が 1 つも無い区切りは
    何も分けない (= 書き忘れ)。
    """
    if not isinstance(rows, list) or not rows or not all(isinstance(row, (list, dict)) and row for row in rows):
        raise PageTypeError(f"{what}: a table is a list of rows, each a list of cells "
                            "(or a band that divides it: { band = \"…\" }), or a CSV file: { data = \"x.csv\" }")
    read = []
    for r, row in enumerate(rows, start=1):
        where = f"{what}: row {r}"
        if isinstance(row, dict):
            if r == 1:
                raise PageTypeError(f"{where}: the heading row is cells in columns; a band divides the rows under it")
            if r == len(rows):
                raise PageTypeError(f"{where}: a band divides the rows under it, and nothing stands under this one")
            read.append([read_band(row, where)])
        else:
            read.append([read_cell(cell, f"{where}, column {c}") for c, cell in enumerate(row, start=1)])
    return read


def _read_table_file(table: dict, what: str, asset: Callable[[str], Path]) -> list[list[str]]:
    """A table read from a CSV among the assets: its first row is the heading row, the rest is the body.

    マスは字のまま (= 数を整形しない。前後の空白だけ落とす)。残す列 (= `columns`) と、特定のマスの字を変える
    注 (= `cells`) は、どちらも CSV の見出しの字と 1 列目の字で指す。**指した先が無い・2 つ以上ある時は止める**
    (= 黙って捨てると、CSV の行の名前が変わった日に注が消えたのに気づけない)。
    """
    only_keys(table, TABLE_DATA_KEYS, what)
    name = table.get("data")
    if not isinstance(name, str) or Path(name).suffix.lower() != ".csv":
        raise PageTypeError(f"{what}: `data` is the name of a CSV file among the assets, not {name!r}")
    lines = _csv_lines(asset(name), name, what)
    if len(lines) < 2:
        raise PageTypeError(f"{what}: {name} needs a heading row and at least one row under it")
    headings = lines[0][1]
    for number, row in lines[1:]:
        if len(row) != len(headings):
            raise PageTypeError(f"{what}: {name}, line {number} has {len(row)} cells and the heading row has "
                                f"{len(headings)} — every row has one cell for each heading")
    grid = [row for _number, row in lines]
    kept = _kept_columns(table.get("columns"), headings, name, what)
    edited: dict[tuple[int, int], int] = {}
    for edit_number, edit in enumerate(_listed(table.get("cells"), "cells", what), start=1):
        where = f"{what}: cells, entry {edit_number}"
        at = _edit_cell(grid, lines, headings, kept, edit, name, where)
        if at in edited:
            raise PageTypeError(f"{where}: this cell is already edited by entry {edited[at]} — one entry for a cell")
        edited[at] = edit_number
    return [[row[index] for index in kept] for row in grid]


def _csv_lines(path: Path, name: str, what: str) -> list[tuple[int, list[str]]]:
    """The rows of a CSV with the line each ended on in the file (= blank rows skipped, cells trimmed)."""
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            return [(reader.line_num, [cell.strip() for cell in row]) for row in reader
                    if any(cell.strip() for cell in row)]
    except UnicodeDecodeError as reason:
        raise PageTypeError(f"{what}: {name} is not UTF-8 text ({reason.reason} at byte {reason.start})") from reason


def _listed(value, key: str, what: str) -> list:
    """What a key holds as a list (= nothing when it is not written)."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise PageTypeError(f"{what}: `{key}` is a list, not {value!r}")
    return value


def _heading_index(headings: list[str], heading, name: str, what: str) -> int:
    """Where a heading of the CSV stands (= its one place; a missing or a doubled heading stops)."""
    found = [index for index, written in enumerate(headings) if isinstance(heading, str) and written == heading.strip()]
    if not found:
        raise PageTypeError(f"{what}: {heading!r} is not a heading of {name} (= its headings are "
                            f"{', '.join(repr(written) for written in headings)})")
    if len(found) > 1:
        raise PageTypeError(f"{what}: {name} has the heading {heading!r} in columns "
                            f"{' and '.join(str(index + 1) for index in found)} — it cannot say which one is meant")
    return found[0]


def _kept_columns(columns, headings: list[str], name: str, what: str) -> list[int]:
    """The columns of the CSV the table keeps, in the order `columns` names them (= every column when it does not)."""
    if columns is None:
        return list(range(len(headings)))
    if not isinstance(columns, list) or not columns:
        raise PageTypeError(f"{what}: `columns` lists the headings of {name} to keep, as in "
                            f'columns = ["method", "value"], not {columns!r}')
    kept = [_heading_index(headings, heading, name, f"{what}: columns") for heading in columns]
    twice = sorted({headings[index] for index in kept if kept.count(index) > 1})
    if twice:
        raise PageTypeError(f"{what}: `columns` names {', '.join(repr(heading) for heading in twice)} twice — "
                            "a column stands once")
    return kept


def _edit_cell(grid: list[list[str]], lines: list[tuple[int, list[str]]], headings: list[str], kept: list[int],
               edit, name: str, what: str) -> tuple[int, int]:
    """One entry of `cells`: the words after a cell's value, or the cell's words in place of its value.

    Returns the cell it changed (= its row and its column in the CSV), so a second entry for it can be refused.
    """
    only_keys(edit, TABLE_CELL_KEYS, what)
    for key in ("row", "column"):
        if not isinstance(edit.get(key), str):
            raise PageTypeError(f"{what}: `{key}` is the words that name the cell, not {edit.get(key)!r}")
    if ("after" in edit) == ("text" in edit):
        raise PageTypeError(f"{what}: a cell takes `after` (= words put after its value) or `text` (= words in place "
                            "of its value), one of the two")
    way = "after" if "after" in edit else "text"
    if not isinstance(edit[way], str):
        raise PageTypeError(f"{what}: `{way}` is words, not {edit[way]!r}")
    column = _heading_index(headings, edit["column"], name, f"{what}, column")
    if column not in kept:
        raise PageTypeError(f"{what}: the column {edit['column']!r} is not kept by `columns`, and a cell of it "
                            "is not in the table")
    rows = [index for index, row in enumerate(grid) if row[0] == edit["row"].strip()]
    if not rows:
        raise PageTypeError(f"{what}: {name} has no row whose first cell is {edit['row']!r}")
    if len(rows) > 1:
        where = " and ".join(str(lines[index][0]) for index in rows)
        raise PageTypeError(f"{what}: {name} has {len(rows)} rows whose first cell is {edit['row']!r} "
                            f"(= lines {where}) — it cannot say which one is meant")
    if rows[0] == 0:
        raise PageTypeError(f"{what}: {edit['row']!r} is the heading row of {name}, and the heading row is not edited")
    row = grid[rows[0]]
    row[column] = row[column] + edit["after"] if way == "after" else edit["text"]
    return rows[0], column


def only_keys(item, allowed: set, what: str, hint: str = "") -> None:
    """Refuse a key nobody reads inside a type's own tables, the way a page's keys are."""
    if not isinstance(item, dict):
        raise PageTypeError(f"{what} is {item!r} — write it as a table of keys")
    unknown = sorted(item.keys() - allowed)
    if unknown:
        raise PageTypeError(
            f"{what} does not take {', '.join(unknown)} (= it accepts "
            f"{', '.join(sorted(allowed))}).{hint}")


def read_weight(item: dict, what: str) -> float:
    """The share a row, a cell or a stage takes (= 1 when it says nothing; a number above 0).

    段・マス・道のりの段のどれの `weight` も、読むのはここ 1 か所 (= 文面も 1 つ)。
    """
    value = item.get("weight", 1)
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
        raise PageTypeError(f"{what}: `weight` is a number above 0 (= a share), not {value!r}")
    return float(value)


def read_tone(spec: Spec, item: dict, what: str, unsaid: str, *, also: tuple[str, ...] = ()) -> str:
    """The tone a table asks for, or `unsaid` when it asks for none.

    書けるのは道具の色の役 (= `TONES`) と、案件が `[theme.grounds]` で名前を付けた地。`also` は、その箱だけが
    選べる地 (= 入れ物の白い地)。
    """
    tone = str(item.get("tone", unsaid))
    named = spec.theme.ground_names()
    if tone not in TONES and tone not in named and tone not in also:
        grounds = (f"; this project names {', '.join(named)} in [theme.grounds]" if named
                   else "; a project may name its own in [theme.grounds]")
        raise PageTypeError(
            f"{what} has tone {tone!r} — a tone is one of the palette's roles: "
            f"{', '.join((*TONES, *also))}{grounds}")
    return tone


#: 箱・棒・矢羽根のどれにも書ける見た目のキー (= 色の役・アイコン・点線・強調)。1 組を全部が読む
LOOK_KEYS = ("tone", "icon", "tentative", "strong")


def _flag(item: dict, key: str, what: str) -> bool:
    value = item.get(key, False)
    if not isinstance(value, bool):
        raise PageTypeError(f"{what}: `{key}` is true or false, not {value!r}")
    return value


def read_style(spec: Spec, item: dict, what: str, unsaid: str, *, also: tuple[str, ...] = ()) -> Style:
    """The four looks a table carries, read here for every part shaped like a box.

    `unsaid` は `tone` を書かなかった時の地で、部品ごとに違う (= 箱は `box`、道のりの段は薄い地か
    到達点の濃い地、線表の棒は空 ― 空は「レーンの色」で、置く側が決める)。

    ⚠ **読むのはここ 1 か所。**部品ごとに読んでいた間は、同じ 4 つを 3 か所が別の順で読み、1 つ足す
    たびに 3 か所を直すことになった。
    """
    return Style(read_tone(spec, item, what, unsaid, also=also) if "tone" in item else unsaid, _icon(spec, item, what),
                 tentative=_flag(item, "tentative", what), strong=_flag(item, "strong", what))


#: アイコンに読める絵 (= 図と同じ。SVG は pptx に入れるのに描き直しの道具が要るので、まだ読まない)
ICON_FORMATS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff")


#: カードの表に書けるキー (= 見出しと本文、見た目の 4 つ、札と字の寄せ)。箱の形をした物のうち、これを読むのは
#: カードと流れ図・道のりのノード (= 同じ箱) だけで、棒と矢羽根は `LOOK_KEYS` だけを読む
CARD_KEYS = ("heading", "body", *LOOK_KEYS, "tag", "align")


def _body(value, what: str) -> tuple[str, bool]:
    """A card's body, and whether it is a list of bullets.

    文字列は段落のまま。配列は 1 件が「•」の 1 行で、本文は行ごとに改行で区切って持つ。

    ⚠ **1 件の中の改行は拒む。**改行を許すと、1 件が点の付く行 2 つに割れて、書いた件数と点の数が合わない。
    """
    if not isinstance(value, (list, tuple)):
        return str(value), False
    items = [str(item).strip() for item in value]
    if not items:
        raise PageTypeError(f"{what}: `body` is an empty list — write the lines, or leave `body` out")
    for number, item in enumerate(items, start=1):
        if not item:
            raise PageTypeError(f"{what}: line {number} of `body` is empty — a bullet says something")
        if "\n" in item:
            raise PageTypeError(f"{what}: line {number} of `body` has a line break — one item is one bullet; "
                                "write it as two items")
    return "\n".join(items), True


def read_card(spec: Spec, item, what: str) -> Card:
    """One card, or one node of a flow or a roadmap (= the same box, written the same two ways).

    書き方は 2 つ ― `["見出し", "本文"]` か、色の役やアイコンを付けるときの
    `{ heading = "…", body = "…", tone = "accent", icon = "device.png", tentative = true,
    strong = true }`。

    表の書き方では見出しも本文も省ける (= 本文だけのカード、相手が書き込む空のカード)。`body` に配列を
    書くと「•」の行、`align = "center"` で中央寄せ、`tag = true` で札 (= 見出しだけを 1 行で置く)。
    """
    if isinstance(item, dict):
        only_keys(item, set(CARD_KEYS), what)
        heading = str(item.get("heading", ""))
        body, bullets = _body(item.get("body", ""), what)
        align = item.get("align", "left")
        if not isinstance(align, str) or align not in CARD_ALIGNS:
            raise PageTypeError(f"{what}: `align` is {' or '.join(repr(name) for name in CARD_ALIGNS)}, not {align!r}")
        style = read_style(spec, item, what, TONES[0])
        tag = _flag(item, "tag", what)
        if tag:
            if not heading.strip():
                raise PageTypeError(f"{what}: a tag is its heading — write the words it carries")
            if body.strip() or style.icon:
                raise PageTypeError(f"{what}: a tag is one line of its heading — it takes no `body` and no `icon`")
        return Card(heading, body, style, tag=tag, align=align, bullets=bullets)
    if isinstance(item, (list, tuple)) and len(item) == 2:
        body, bullets = _body(item[1], what)
        return Card(str(item[0]), body, bullets=bullets)
    raise PageTypeError(
        f"{what} is {item!r} — write it as [\"heading\", \"body\"], or as a table "
        "{ heading = …, body = …, tone = …, icon = … }")


#: 入れ物の表に書けるキー (= 見出し・線・中の段、カードと同じ見た目のうちアイコンを除く 3 つ)。中の段 (= `rows`) は
#: `compose` が自分の段とマスの読み方で読むので、ここでは在ることだけを確かめる
PANEL_KEYS = ("heading", "rule", "rows", *(key for key in LOOK_KEYS if key != "icon"))


def read_panel(spec: Spec, item, what: str) -> Panel:
    """A panel as written: `{ tone = …, heading = "…", rule = true, rows = [ … ] }` (= all but `rows` may be left out).

    見た目 (= `tone` `tentative` `strong`) はカードと同じ 1 つの読み方 (= `read_style`)。入れ物は、それに加えて白い地
    (= `tone = "paper"`) を選べる。`rule` は見出しの下の線で、
    見出しが無ければ引く場所が無いので止める。
    """
    only_keys(item, set(PANEL_KEYS), what)
    rows = item.get("rows")
    if not isinstance(rows, list) or not rows:
        raise PageTypeError(f"{what}: a panel holds rows — write `rows` with at least one row of cells")
    heading = item.get("heading", "")
    if not isinstance(heading, str):
        raise PageTypeError(f"{what}: `heading` is the words in its top left corner, not {heading!r}")
    rule = _flag(item, "rule", what)
    if rule and not heading.strip():
        raise PageTypeError(f"{what}: `rule` is the line under the heading, and this panel has no heading")
    return Panel(heading.strip(), read_style(spec, item, what, TONES[0], also=(PAPER,)), rule)


def _icon(spec: Spec, item: dict, what: str) -> tuple[Path, float] | None:
    """The picture a box carries beside its words, read like any figure (= from the assets)."""
    if "icon" not in item:
        return None
    name = str(item["icon"])
    if Path(name).suffix.lower() not in ICON_FORMATS:
        raise PageTypeError(
            f"{what} has the icon {name!r} — an icon is a picture file "
            f"({' / '.join(ICON_FORMATS)}); export an SVG as PNG, at a few times the size it "
            "is shown")
    path = spec.asset(name)
    return path, spec.aspect(path)
