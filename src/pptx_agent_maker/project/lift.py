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

from ..deck.text import STAND_IN, decide, stand_in
from .recipes import FILENAME as RECIPES
from .recipes import HEADER, recipe_block
from .recipes import load as load_recipes

#: 頁が持っていてよい関係 (= これ以外は、表やグラフの元データなどを連れてくる)
PLAIN_RELS = ("slideLayout", "image", "notesSlide", "hyperlink")


class LiftError(ValueError):
    """What was asked cannot be lifted without carrying the project along."""


@dataclass
class Lifted:
    """What went into the template, for the person to read over."""

    recipes: list[str] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)
    #: 上げた物ごとに (元の文言, テンプレートに入った文言) の並び
    words: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    stale: list[str] = field(default_factory=list)
    #: 上げる前のテンプレートの控え (= 戻すなら、ここの file を folder へ戻す)
    kept_at: Path | None = None


def lift(project: Path | str, template: Path | str, *, recipes: list[str] = (),
         pages: list[tuple[str, int]] = (), replace: list[tuple[str, str]] = (),
         keep: list[str] = ()) -> Lifted:
    """Lift recipes and built pages from `project` into the template folder `template`."""
    from ..deck import Deck

    project, template = Path(project), Path(template).expanduser()
    specimen = template / "specimen.pptx"
    if not specimen.is_file():
        raise LiftError(f"{template} holds no specimen.pptx — lift into a template folder")
    if not recipes and not pages:
        raise LiftError("nothing to lift: name a --recipe or a --page")
    for old, new in replace:
        if not old or not new or old == new:
            raise LiftError(f"--replace {old!r}={new!r}: give the project's word and what stands in for it")

    hits = {old: 0 for old, _new in replace}
    keep = {word.strip() for word in keep}
    names: dict[str, str] = {}  # 元の文言 → 仮の語 (= 頁と recipe で番号を共有する)
    result = Lifted()

    # recipe (= 文言の中の語を置き換える。穴 `{method}` はそのまま残る)
    new_recipes = None
    if recipes:
        own, theirs = load_recipes(project), load_recipes(template)
        path = template / RECIPES
        text = path.read_text(encoding="utf-8") if path.is_file() else HEADER
        if not text.endswith("\n"):
            text += "\n"
        for name in recipes:
            if name not in own:
                raise LiftError(f"the project has no recipe named {name!r}")
            if name in theirs or name in result.recipes:
                raise LiftError(f"the template already has a recipe named {name!r}")
            placed: list[tuple[str, str]] = []
            # 型の名前は文言ではない (= 仮の語にすると recipe が組めなくなる)
            shaped = {key: value if key == "type" else
                      _decided(value, keep, replace, names, hits, placed)
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


def _decided(value, keep, replace, names, hits, placed):
    """A recipe's words under the same rule as a page's (= `decide`)."""
    if isinstance(value, str):
        if not value.strip():
            return value
        new = decide(value, keep=keep, replace=replace, names=names, hits=hits)
        placed.append((value, new))
        return new
    if isinstance(value, list):
        return [_decided(item, keep, replace, names, hits, placed) for item in value]
    if isinstance(value, dict):
        return {key: _decided(item, keep, replace, names, hits, placed)
                for key, item in value.items()}
    return value


def _plain(deck: Path, number: int) -> None:
    """Refuse a page whose relationships would carry data along (= charts, embedded files)."""
    from ..deck.archive import Archive

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
    """The template's settings with `words` added to `[checks] stale_words`."""
    text = settings.read_text(encoding="utf-8") if settings.is_file() else ""
    current = tomllib.loads(text).get("checks", {}).get("stale_words", []) if text else []
    wanted = current + [w for w in words if w not in current]
    line = "stale_words = [" + ", ".join(_quote(w) for w in wanted) + "]"
    if re.search(r"(?m)^stale_words\s*=.*$", text):
        text = re.sub(r"(?m)^stale_words\s*=.*$", lambda _m: line, text, count=1)
    elif re.search(r"(?m)^\[checks\]\s*$", text):
        text = re.sub(r"(?m)^\[checks\]\s*$", lambda m: m.group(0) + "\n" + line, text, count=1)
    else:
        text = text.rstrip("\n") + "\n\n# テンプレートが残した語。差し替え忘れたら検査が止める。\n[checks]\n" + line + "\n"
    tomllib.loads(text)  # 壊した設定を書かない
    return text


def _quote(word: str) -> str:
    return '"' + word.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _keep_previous(template: Path) -> Path:
    """Copy the template as it is now into `_archive/<time>/` (= a lift can be undone)."""
    import shutil
    from datetime import datetime

    where = template / "_archive" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    where.mkdir(parents=True)
    for name in ("specimen.pptx", RECIPES, "workspace.toml"):
        if (template / name).is_file():
            shutil.copy2(template / name, where / name)
    return where


def _write(path: Path, text: str) -> None:
    staged = path.with_name(f".{path.name}.lifting")
    staged.write_text(text, encoding="utf-8")
    os.replace(staged, path)


def _replace_file(source: Path, target: Path) -> None:
    staged = target.with_name(f".{target.name}.lifting")
    staged.write_bytes(source.read_bytes())
    os.replace(staged, target)
