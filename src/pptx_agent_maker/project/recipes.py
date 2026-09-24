"""A page the project has written twice, kept once.

**型は頁の形を決めるが、毎週くり返す頁の中身までは決めない。**同じ結果頁を毎週作るとき、
型だけでは manifest の塊を毎週複製して値を書き換えることになり、前の世代で頁 script が
週ごとに複製されたのと同じものが、今度は manifest に溜まる。前の世代では上げる口が重く、
複製して少し直すほうが安かったので、昇格は 1 度も起きなかった。

ここでは案件が `recipes.toml` に**頁の決まった部分**を 1 回だけ書き、manifest の頁は
**毎回変わる部分**だけを渡す:

    # recipes.toml
    [recipes.result]
    type = "figures"
    title = "{method} の結果"
    footer = "採点表から"

    # w3.toml
    [[pages]]
    kind = "recipe"
    recipe = "result"
    fill = { method = "手法 A" }
    figures = [["a.png", "正面"], ["b.png", "背面"]]

⚠ **頁は recipe が決めたキーを書き換えられない。**書き換えられると、同じ recipe の頁が
週ごとに少しずつ違う形になる (= recipe を作った意味が消える)。違う形が要るなら recipe を
直すか、別の recipe を上げる。

上げるのは `promote` 1 回 ― 同じ形の頁を 2 か所以上指すと、全部で同じ値のキーが recipe に
なり、違うキーだけが各頁に残り、**元の頁は recipe を呼ぶ形に書き換わる**。前の世代は
この書き換えが人の手だったので、上げた後も古いコピーが残り続けた。
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

FILENAME = "recipes.toml"

#: 頁の運び方に属するキー (= recipe には入れない)
CARRIAGE = frozenset({"kind", "page", "deck", "replace", "why", "recipe", "fill"})
#: 文言の中の穴 (= `{method}`)
HOLE = re.compile(r"\{(\w+)\}")
#: TOML の表の見出し行 (= `[[pages]]` / `[recipes.result]` / `[theme]`)
TABLE_HEAD = re.compile(r"^\[\[?\s*[A-Za-z0-9_.\- ]+\s*\]\]?\s*(#.*)?$")


class RecipeError(ValueError):
    """A recipe, or a page calling one, cannot be read as a page."""


def load(root: Path | str) -> dict[str, dict]:
    """Every recipe the project has, by name (= none when there is no file)."""
    path = Path(root) / FILENAME
    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    unknown = sorted(set(data) - {"recipes"})
    if unknown:
        raise RecipeError(f"{FILENAME}: only [recipes.<name>] tables belong here, not {unknown}")
    recipes = data.get("recipes", {})
    for name, recipe in recipes.items():
        if not recipe.get("type"):
            raise RecipeError(f"{FILENAME}: recipe {name!r} has no `type`")
        carried = sorted(set(recipe) & CARRIAGE)
        if carried:
            raise RecipeError(
                f"{FILENAME}: recipe {name!r} carries {', '.join(carried)} — those belong "
                "to the page that calls it, not to the page's shape"
            )
    return recipes


def expand(where: str, page: dict, recipes: dict[str, dict]) -> dict:
    """The declaration a `kind = "recipe"` page stands for.

    ⚠ **穴を埋め残さない / 使わない値を黙って捨てない。**どちらも「書いたつもりで頁に無い」
    の形で、型が知らないキーを拒むのと同じ理由で止める。
    """
    name = str(page.get("recipe", ""))
    if name not in recipes:
        known = ", ".join(sorted(recipes)) or "none — the project has no recipes.toml yet"
        raise RecipeError(f"{where}: no recipe named {name!r} (= the project has: {known})")
    recipe = recipes[name]
    own = {key: value for key, value in page.items() if key not in CARRIAGE}
    clash = sorted(set(own) & set(recipe))
    if clash:
        raise RecipeError(
            f"{where}: recipe {name!r} already fixes {', '.join(clash)}. A page that changes "
            "what its recipe fixes drifts from the others; change the recipe, or promote "
            "another one"
        )
    fill = {str(k): str(v) for k, v in (page.get("fill") or {}).items()}
    used: set[str] = set()
    filled = {key: _fill(value, fill, used, f"{where}: {key}") for key, value in recipe.items()}
    unused = sorted(set(fill) - used)
    if unused:
        raise RecipeError(
            f"{where}: `fill` names {', '.join(unused)}, which recipe {name!r} has no "
            "hole for"
        )
    return {**filled, **own}


def _fill(value, fill: dict[str, str], used: set[str], where: str):
    if isinstance(value, str):
        def swap(match: re.Match) -> str:
            hole = match.group(1)
            if hole not in fill:
                raise RecipeError(f"{where}: the recipe leaves {{{hole}}} open; give it in `fill`")
            used.add(hole)
            return fill[hole]
        return HOLE.sub(swap, value)
    if isinstance(value, list):
        return [_fill(item, fill, used, where) for item in value]
    if isinstance(value, dict):
        return {key: _fill(item, fill, used, where) for key, item in value.items()}
    return value


# -- promote ---------------------------------------------------------------


def split(pages: list[dict]) -> tuple[dict, list[dict]]:
    """What the pages share (= the recipe), and what each keeps for itself.

    同じ値のキーは全部 recipe へ、1 つでも違うキーは全部の頁に残す。題の一部だけが違う
    ような場合は、ここでは穴を推測しない (= 題ごと頁に残る)。穴を空けるのは人の判断。
    """
    if len(pages) < 2:
        raise RecipeError("promote takes at least two pages: a shape used once is not yet a shape")
    kinds = {str(page.get("kind")) for page in pages}
    if kinds != {"declare"}:
        raise RecipeError(
            "promote takes declared pages only (= a copied or imported page has no "
            f"declaration to share; got {', '.join(sorted(kinds))})"
        )
    types = {str(page.get("type")) for page in pages}
    if len(types) != 1:
        raise RecipeError(f"these pages are not one shape: their types differ ({', '.join(sorted(types))})")
    keys = set().union(*(set(page) - CARRIAGE for page in pages))
    shared = {key for key in keys
              if all(key in page for page in pages)
              and all(page[key] == pages[0][key] for page in pages)}
    # 並びは元の頁に書かれた順 (= `type` が先頭に来る。辞書順だと末尾に沈む)
    recipe = {key: value for key, value in pages[0].items() if key in shared}
    rest = []
    for page in pages:
        mine = {key: value for key, value in page.items()
                if key not in shared and key not in {"kind"}}
        rest.append(mine)
    return recipe, rest


def append_recipe(root: Path | str, name: str, recipe: dict) -> str:
    """The recipes file with one more recipe at the end (= returned, not yet written)."""
    path = Path(root) / FILENAME
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise RecipeError(f"{name!r}: a recipe name is letters, digits, - and _")
    if name in load(root):
        raise RecipeError(f"{FILENAME} already has a recipe named {name!r}")
    text = path.read_text(encoding="utf-8") if path.is_file() else HEADER
    if text and not text.endswith("\n"):
        text += "\n"
    block = [f"\n[recipes.{name}]"] + [f"{_key(k)} = {dump(v)}" for k, v in recipe.items()]
    return text + "\n".join(block) + "\n"


HEADER = """\
# Pages this project writes the same way every round, kept once.
# A manifest page calls one with `kind = "recipe"` and gives only what changes.
"""


def page_block(page: dict) -> str:
    """One `[[pages]]` block calling a recipe."""
    order = ["kind", "recipe", "fill"]
    lines = ["[[pages]]", 'kind = "recipe"']
    for key in order[1:]:
        if key in page:
            lines.append(f"{_key(key)} = {dump(page[key])}")
    for key, value in page.items():
        if key not in order:
            lines.append(f"{_key(key)} = {dump(value)}")
    return "\n".join(lines) + "\n"


def replace_block(text: str, number: int, block: str) -> str:
    """The manifest text with its Nth `[[pages]]` block swapped for another.

    ⚠ **次の頁の前に置かれた注記は消さない。**塊の終わりは次の見出しの手前だが、
    その直前の空行と `#` の行は次の頁 (や、コメントにした見本) のものなので残す。
    """
    lines = text.splitlines(keepends=True)
    heads = [i for i, line in enumerate(lines) if line.strip() == "[[pages]]"]
    if not 1 <= number <= len(heads):
        raise RecipeError(f"the manifest has {len(heads)} pages; asked for page {number}")
    start = heads[number - 1]
    # 見出しの形だけを区切りにする (= 複数行の配列の `["a.png", "x"],` を見出しと読まない)
    end = next((i for i in range(start + 1, len(lines))
                if TABLE_HEAD.match(lines[i])), len(lines))
    while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    return "".join(lines[:start]) + block + "".join(lines[end:])


# -- a small TOML writer (= tomllib reads only) ----------------------------


def dump(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        escaped = (value.replace("\\", "\\\\").replace('"', '\\"')
                   .replace("\n", "\\n").replace("\t", "\\t"))
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(dump(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{_key(k)} = {dump(v)}" for k, v in value.items()) + " }"
    raise RecipeError(f"cannot write {type(value).__name__} into TOML")


def _key(key: str) -> str:
    return key if re.fullmatch(r"[A-Za-z0-9_-]+", key) else dump(key)


# -- the one command -------------------------------------------------------


def promote(root: Path | str, name: str, targets: list[tuple[str, int]]) -> list[Path]:
    """Lift the pages at `targets` into recipe `name`, and rewrite them to call it.

    ⚠ **書く前に、書き換えた後の manifest を読み直して元と比べる。**頁ごとに展開した中身が
    元の宣言と 1 つでも違えば、1 file も書かずに止める (= 上げたら頁が変わった、を作らない)。
    返すのは書いた file。
    """
    from .manifest import Manifest  # manifest は recipes を読むので、ここでだけ引く

    root = Path(root)
    texts: dict[Path, str] = {}
    pages: list[dict] = []
    for manifest, number in targets:
        path = root / (manifest if manifest.endswith(".toml") else f"{manifest}.toml")
        if not path.is_file():
            raise RecipeError(f"no manifest at {path}")
        texts.setdefault(path, path.read_text(encoding="utf-8"))
        listed = tomllib.loads(texts[path]).get("pages", [])
        if not 1 <= number <= len(listed):
            raise RecipeError(f"{path.name} has {len(listed)} pages; asked for page {number}")
        pages.append(listed[number - 1])
    if len(set(targets)) != len(targets):
        raise RecipeError("the same page is named twice")

    recipe, rest = split(pages)
    new_recipes = append_recipe(root, name, recipe)
    rewritten = dict(texts)
    # 後ろの頁から差し替える (= 塊の長さが変わっても、前の頁の位置はずれない)
    for (manifest, number), mine in sorted(zip(targets, rest), key=lambda t: -t[0][1]):
        path = root / (manifest if manifest.endswith(".toml") else f"{manifest}.toml")
        rewritten[path] = replace_block(rewritten[path], number,
                                        page_block({"recipe": name, **mine}))

    import tempfile
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        (scratch / FILENAME).write_text(new_recipes, encoding="utf-8")
        for path in texts:
            before = Manifest.load(path)
            (scratch / path.name).write_text(rewritten[path], encoding="utf-8")
            try:
                after = Manifest.load(scratch / path.name)
            except ValueError as error:
                raise RecipeError(f"the rewritten {path.name} does not read back: {error}") from error
            if len(before.entries) != len(after.entries):
                raise RecipeError(f"the rewritten {path.name} lost or gained a page")
            for index, (old, new) in enumerate(zip(before.entries, after.entries), start=1):
                if (old.kind, old.data, old.replace, old.why) != (new.kind, new.data, new.replace, new.why):
                    raise RecipeError(
                        f"{path.name} page {index} would change if promoted; nothing was written"
                    )

    (root / FILENAME).write_text(new_recipes, encoding="utf-8")
    for path, text in rewritten.items():
        path.write_text(text, encoding="utf-8")
    return [root / FILENAME, *rewritten]
