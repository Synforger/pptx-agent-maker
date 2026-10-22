"""Lifting what one project made into the template every later project starts from.

**粒度が違う 2 つの昇格。**案件の中での登録 (`promote`) は頻繁で、案件の語のまま上げてよい。
こちらは稀で、上げた物が**次の案件すべて**に配られる ― 別の先方の資料に、前の先方の語や
数字が混ざる経路になる。だから上げる時に案件のものを抜く:

- **文言は既定で全部抜く。**表の値も含め、run ごとに `<文言 1>` `<文言 2>` … という仮の語に
  なる (= 同じ文言には同じ番号)。残すのは `--keep` で指した語 (= 章の見出し、表の見出し) と、
  `--replace "手法 A=<手法名>"` が当たった run だけ。どれが案件の語かをツールは見分けられない
  ので、**指し忘れた時に抜ける側へ倒す** ― 残し忘れは書き直せば済むが、抜き忘れは前の先方の
  中身が次の先方に届く
- **絵**は全部、同じ比の灰色の仮の絵になる (= 絵は案件の中身そのもの)
- 図形の代替テキストは消える (= 頁には見えず、file 名が入っていることが多い)
- 仮の語の頭と `--replace` の置き換え先はテンプレートの `stale_words` に入り、次の案件で
  埋め忘れを検査が止める
- 1 度も当たらなかった `--replace` は止める (= 綴り違いで、置き換えたつもりの語が仮の語になる)

上げた後は、何が何になったかを全部出す ― 残す語を決めるのは人。

頁はテンプレート (`specimen.pptx`) の末尾に足し、次の案件は `copy` で呼ぶ。recipe は
テンプレートの folder の `recipes.toml` へ足し、`init --specimen <folder>` が一緒に配る。
"""

from __future__ import annotations

import os
import re
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from ...deck.pages.text import STAND_IN, decide, stand_in
from ..files.recipes import FILENAME as RECIPES
from ..files.recipes import HEADER, HOLE, recipe_block
from ..files.recipes import load as load_recipes
from ..files.recipes import load_parts

#: 頁が持っていてよい関係 (= これ以外は、表やグラフの元データなどを連れてくる)
PLAIN_RELS = ("slideLayout", "image", "notesSlide", "hyperlink")


class LiftError(ValueError):
    """What was asked cannot be lifted without carrying the project along."""


@dataclass
class Lifted:
    """What went into the template, for the person to read over."""

    recipes: list[str] = field(default_factory=list)
    parts: list[str] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)
    #: 上げた物ごとに (元の文言, テンプレートに入った文言) の並び
    words: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    stale: list[str] = field(default_factory=list)
    #: 上げる前のテンプレートの控え (= 戻すなら、ここの file を folder へ戻す)
    kept_at: Path | None = None


def lift(project: Path | str, template: Path | str, *, recipes: list[str] = (),
         pages: list[tuple[str, int]] = (), replace: list[tuple[str, str]] = (),
         keep: list[str] = (), parts: list[str] = ()) -> Lifted:
    """Lift recipes, parts and built pages from `project` into the template folder `template`."""
    from ...deck import Deck

    project, template = Path(project), Path(template).expanduser()
    specimen = template / "specimen.pptx"
    if not specimen.is_file():
        raise LiftError(f"{template} holds no specimen.pptx — lift into a template folder")
    if not recipes and not pages and not parts:
        raise LiftError("nothing to lift: name a --recipe, a --part or a --page")
    for old, new in replace:
        if not old or not new or old == new:
            raise LiftError(f"--replace {old!r}={new!r}: give the project's word and what stands in for it")

    hits = {old: 0 for old, _new in replace}
    keep = {word.strip() for word in keep}
    names: dict[str, str] = {}  # 元の文言 → 仮の語 (= 頁と recipe で番号を共有する)
    result = Lifted()

    # recipe (= 文言の中の語を置き換える。穴 `{method}` はそのまま残る)
    new_recipes = None
    if recipes or parts:
        own, theirs = load_recipes(project), load_recipes(template)
        path = template / RECIPES
        text = path.read_text(encoding="utf-8") if path.is_file() else HEADER
        if not text.endswith("\n"):
            text += "\n"
        # 部品 (= マスの recipe) も、頁の recipe と同じく文言の中の語を置き換えて上げる
        own_parts, their_parts = load_parts(project), load_parts(template)
        for name in parts:
            if name not in own_parts:
                raise LiftError(f"the project has no part named {name!r}")
            if name in their_parts or name in result.parts:
                raise LiftError(f"the template already has a part named {name!r}")
            placed: list[tuple[str, str]] = []
            shaped = {key: _decided(value, keep, replace, names, hits, placed, key)
                      for key, value in own_parts[name].items()}
            text += recipe_block(name, shaped, "parts")
            result.parts.append(name)
            result.words[f"part {name}"] = placed
        for name in recipes:
            if name not in own:
                raise LiftError(f"the project has no recipe named {name!r}")
            if name in theirs or name in result.recipes:
                raise LiftError(f"the template already has a recipe named {name!r}")
            placed: list[tuple[str, str]] = []
            # 型の名前は文言ではない (= 仮の語にすると recipe が組めなくなる)
            shaped = {key: _decided(value, keep, replace, names, hits, placed, key)
                      for key, value in own[name].items()}
            text += recipe_block(name, shaped)
            result.recipes.append(name)
            result.words[f"recipe {name}"] = placed
        new_recipes = text

    # 頁 (= 元の頁を全部残し、末尾に足す)
    staged_deck = None
    scratch = tempfile.TemporaryDirectory()
    try:
        if pages:
            staged_deck = Path(scratch.name) / "specimen.pptx"
            with Deck.open(specimen, staged_deck) as deck:
                before = deck.specimen_pages
                for number in range(1, before + 1):
                    deck.keep(number)
                for position, (name, number) in enumerate(pages, start=before + 1):
                    source = project / name
                    if not source.is_file():
                        raise LiftError(f"no deck at {source}")
                    _plain(source, number)
                    page = deck.bring(source, number)
                    placed = stand_in(page.path, keep=keep, replace=replace,
                                      names=names, hits=hits)
                    page.blank_pictures(Path(scratch.name))
                    page.forget_descriptions()
                    result.pages.append(position)
                    result.words[f"specimen page {position}"] = placed

        missed = [old for old, count in hits.items() if not count]
        if missed:
            raise LiftError(
                f"--replace never matched {', '.join(repr(m) for m in missed)} in what was "
                "lifted — a misspelt word stays in the template under its real name"
            )

        # ここまで来たら書く (= 途中で止まった時に、テンプレートを半端にしない)
        stale = [new for _old, new in replace] + ([STAND_IN] if names else [])
        settings = template / "workspace.toml"
        new_settings = _with_stale_words(settings, stale) if stale else None
        result.kept_at = _keep_previous(template)
        if staged_deck is not None:
            _replace_file(staged_deck, specimen)
        if new_recipes is not None:
            _write(template / RECIPES, new_recipes)
        if new_settings is not None:
            _write(settings, new_settings)
        result.stale = stale
    finally:
        scratch.cleanup()
    return result


#: 文言ではなく、決まった語から選ぶ値のキー (= 仮の語にすると、その recipe や部品が組めなくなる)
CHOICES = frozenset({"type", "role", "tone", "kind", "direction", "numbers", "highlight_tone", "use"})


def _decided(value, keep, replace, names, hits, placed, key: str = ""):
    """A recipe's words under the same rule as a page's (= `decide`).

    選ぶ値 (= `CHOICES`) と、穴だけの値 (= `{figure}`) はそのまま上がる ― どちらも案件の言葉を持たない。
    """
    if key in CHOICES:
        return value
    if isinstance(value, str):
        if not value.strip() or HOLE.fullmatch(value.strip()):
            return value
        new = decide(value, keep=keep, replace=replace, names=names, hits=hits)
        placed.append((value, new))
        return new
    if isinstance(value, list):
        return [_decided(item, keep, replace, names, hits, placed) for item in value]
    if isinstance(value, dict):
        return {name: _decided(item, keep, replace, names, hits, placed, name)
                for name, item in value.items()}
    return value


def _plain(deck: Path, number: int) -> None:
    """Refuse a page whose relationships would carry data along (= charts, embedded files)."""
    from ..._common.archive import Archive

    order = Archive(deck.parent).order_of(deck)
    if not 1 <= number <= len(order):
        raise LiftError(f"{deck.name} has {len(order)} pages; asked for {number}")
    with zipfile.ZipFile(deck) as archive:
        rels = archive.read(f"ppt/slides/_rels/{order[number - 1]}.rels").decode("utf-8")
    kinds = {kind.rsplit("/", 1)[-1] for kind in re.findall(r'Type="([^"]+)"', rels)}
    carried = sorted(kinds - set(PLAIN_RELS))
    if carried:
        raise LiftError(
            f"{deck.name} page {number} carries {', '.join(carried)} — those hold their own "
            "data (a chart's numbers, an embedded file) that lifting would take along"
        )


def _with_stale_words(settings: Path, words: list[str]) -> str:
    """The template's settings with `words` added to `[checks] stale_words`.

    ⚠ **配列は、人が書いた形のまま末尾に足す。**1 行目だけを書き直すと、複数行に並べた配列の 2 行目から
    先が宙に浮き、設定が読めなくなった。配列の終わりは文字列とコメントを読み飛ばして探し、並べ方
    (= 1 行か、1 語 1 行か) と中のコメントは残す。
    """
    text = settings.read_text(encoding="utf-8") if settings.is_file() else ""
    current = tomllib.loads(text).get("checks", {}).get("stale_words", []) if text else []
    added = [w for w in words if w not in current]
    key = re.search(r"(?m)^[ \t]*stale_words[ \t]*=[ \t]*(?=\[)", text)
    if key:
        if added:
            text = _appended(text, key.end(), added)
    elif re.search(r"(?m)^\[checks\]\s*$", text):
        line = "stale_words = [" + ", ".join(_quote(w) for w in added) + "]"
        text = re.sub(r"(?m)^\[checks\]\s*$", lambda m: m.group(0) + "\n" + line, text, count=1)
    else:
        line = "stale_words = [" + ", ".join(_quote(w) for w in added) + "]"
        text = text.rstrip("\n") + "\n\n# テンプレートが残した語。差し替え忘れたら検査が止める。\n[checks]\n" + line + "\n"
    # 壊した設定も、語が入らなかった設定も書かない (= 別の表の `stale_words` を書き換えた時など)
    landed = tomllib.loads(text).get("checks", {}).get("stale_words")
    if landed != current + added:
        raise LiftError(f"{settings}: could not add {', '.join(map(repr, added))} to [checks] stale_words "
                        "— add them by hand and lift again")
    return text


def _appended(text: str, start: int, words: list[str]) -> str:
    """`text` with `words` added at the end of the array that opens at `start`."""
    end, last, comma = _array_end(text, start)
    quoted = [_quote(w) for w in words]
    if "\n" not in text[start:end]:  # 1 行の配列 (= 語は同じ行に続ける)
        inner = text[start + 1:end].rstrip()
        joint = "" if inner == "" else " " if inner.endswith(",") else ", "
        return text[:start + 1] + inner + joint + ", ".join(quoted) + text[end:]
    # 複数行の配列 (= 最後の語の行と同じ字下げで、1 語 1 行に足す)
    line_start = text.rfind("\n", 0, last if last else end) + 1
    indent = re.match(r"[ \t]*", text[line_start:]).group(0) if last else "    "
    lines = "".join(f"{indent}{q},\n" for q in quoted)
    closing = text.rfind("\n", 0, end) + 1
    if text[closing:end].strip():  # `]` が最後の語と同じ行に在る
        lines, closing = "\n" + lines, end
    head = text[:closing]
    if last and not comma:
        head = head[:last] + "," + head[last:]
    return head + lines + text[closing:]


def _array_end(text: str, start: int) -> tuple[int, int, bool]:
    """Where the TOML array opening at `text[start]` closes, where its last value ends (0 if empty),
    and whether a comma follows that value."""
    depth, at, last, comma = 0, start, 0, False
    while at < len(text):
        char = text[at]
        if char == "#":
            at = text.find("\n", at)
            if at < 0:
                break
            continue
        if char in "\"'":
            fence = char * 3 if text.startswith(char * 3, at) else char
            at += len(fence)
            while at < len(text) and not text.startswith(fence, at):
                at += 2 if char == '"' and text[at] == "\\" else 1
            at += len(fence)
            if depth == 1:
                last, comma = at, False
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return at, last, comma
            if depth == 1:
                last, comma = at + 1, False
        elif char == "," and depth == 1:
            comma = True
        elif not char.isspace() and depth == 1:
            last, comma = at + 1, False
        at += 1
    raise LiftError("the settings' stale_words array never closes")


def _quote(word: str) -> str:
    return '"' + word.replace("\\", "\\\\").replace('"', '\\"') + '"'


#: 控えを残す世代の数。取り消したいのは直前の上げで、何十回も前の物ではない
KEPT = 3
#: 控えの folder の名前 (= 上げた時刻)。この形の名前だけを数え、消す
_COPY = re.compile(r"\d{8}-\d{6}-\d{6}")


def _keep_previous(template: Path) -> Path:
    """Copy the template as it is now into `_archive/<time>/` (= a lift can be undone).

    ⚠ **残すのは新しい方から `KEPT` 世代。**控えは上げるたびに 1 つ増え、消す所が無かった ― テンプレートの
    folder は案件に配る物で、そこに見本の写しが際限なく貯まった。古い物から消すのは、ここが付けた名前
    (= 時刻) の folder だけ。人が `_archive/` に置いた物には触らない。
    """
    import shutil
    from datetime import datetime

    where = template / "_archive" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    where.mkdir(parents=True)
    for name in ("specimen.pptx", RECIPES, "workspace.toml"):
        if (template / name).is_file():
            shutil.copy2(template / name, where / name)
    copies = sorted(path for path in where.parent.iterdir()
                    if path.is_dir() and _COPY.fullmatch(path.name))
    for old in copies[:-KEPT]:
        shutil.rmtree(old)
    return where


def _write(path: Path, text: str) -> None:
    staged = path.with_name(f".{path.name}.lifting")
    staged.write_text(text, encoding="utf-8")
    os.replace(staged, path)


def _replace_file(source: Path, target: Path) -> None:
    staged = target.with_name(f".{target.name}.lifting")
    staged.write_bytes(source.read_bytes())
    os.replace(staged, target)
