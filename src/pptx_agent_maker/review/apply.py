"""Taking what a person changed in PowerPoint back into the manifest.

**人が触るのは PowerPoint で、その差分を manifest に戻すのはエージェントの仕事。**
取り込みを人に残すと、直した版と manifest の 2 つが真値になり、次の build が
どちらかを消す。ここは頁ごとに、直しの種類で写し方を決める:

- **文言だけ** ― 型で組んだ頁は宣言の値そのものを直す (= 値が 1 か所に 1 度だけ在るとき)。
  それ以外は `replace` に足す (= 前の置換の行き先を直したのなら、その対を直す)
- **絵だけ** (= 複製・持ち込みの頁) ― 新しい絵を `assets/<回>/` に取り出し、`pictures` に書く
- **それ以外** (= 位置・大きさ・書式、新しい場所の文字、足した図形) ― manifest では書けない。
  その頁は**人が整えた版を正とし**、控えた手直し版からの `import` に切り替える
- **足した頁**は、その位置に手直し版からの `import` を差し込む。**消した頁**は manifest から消す

⚠ **書く前に焼き直して、手直し版と全頁の文言と絵が一致することを確かめる。**1 か所でも
違えば 1 file も書かずに止める (= 取り込んだつもりで直しが消える、を作らない)。
"""

from __future__ import annotations

import difflib
import os
import re
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from ..checks.slide import read
from ..deck.archive import Archive
from ..deck.swap import NS, pictures
from ..project.manifest import Manifest, ManifestError
from ..project.recipes import TABLE_HEAD, dump, toml_key
from .fold import keep_safe
from .ledger import last_machine_build, remember, touched_by_hand

#: 形を比べる前に落とすもの (= 保存のたびに PowerPoint が書き換える印と、文言そのもの)
_UNSHAPE = (
    (re.compile(r"(<a:t\b[^>]*(?<!/)>).*?(</a:t>)", re.S), r"\1\2"),
    (re.compile(r'\s(?:dirty|err|lang|altLang|smtClean|smtId|noProof|bmk)="[^"]*"'), ""),
    (re.compile(r'\bid="\d+"'), 'id="#"'),
    (re.compile(r'name="([^"\d]+)\d+"'), r'name="\1#"'),
    (re.compile(r'r:(embed|link|id)="[^"]*"'), r'r:\1=""'),
    (re.compile(r"<(a|p):extLst>.*?</\1:extLst>", re.S), ""),
    (re.compile(r"<a:endParaRPr\b[^>]*/>"), ""),
    (re.compile(r"<a:endParaRPr\b.*?</a:endParaRPr>", re.S), ""),
)


class ApplyError(ValueError):
    """The edit cannot be taken in without losing some of it."""


@dataclass
class Applied:
    """What was done to each page, for the person to read."""

    manifest: Path | None = None
    kept_at: Path | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Page:
    texts: tuple[str, ...]
    shape: str
    pictures: tuple[bytes, ...]
    picture_names: tuple[str, ...]


def apply(workspace, deck_name: str) -> Applied:
    """Fold a hand-edited deck back into the manifest that builds it."""
    edited = workspace.out(deck_name if deck_name.endswith(".pptx") else f"{deck_name}.pptx")
    if not touched_by_hand(edited):
        raise ApplyError(f"{edited.name} is as the toolkit built it — nothing to take in")
    reference = last_machine_build(edited)
    if reference is None:
        raise ApplyError(f"there is no copy of what the toolkit last built as {edited.name}")
    manifest_path = _manifest_for(workspace, edited.name)
    manifest = Manifest.load(manifest_path)
    raw_pages = tomllib.loads(manifest_path.read_text(encoding="utf-8")).get("pages", [])

    result = Applied(manifest=manifest_path)
    shelved = keep_safe(edited)
    result.kept_at = shelved
    shelf = shelved.relative_to(workspace.root).as_posix()

    ours, theirs = _pages(reference), _pages(shelved)
    if len(ours) != len(manifest.entries):
        raise ApplyError(
            f"{reference.name} has {len(ours)} pages but {manifest_path.name} has "
            f"{len(manifest.entries)} — the manifest changed since the deck was built")

    new_pages: list[dict | int] = []   # int = 元の頁をそのまま (= 番号は manifest の 0 始まり)
    written_assets: list[Path] = []
    matcher = difflib.SequenceMatcher(None, [p.texts for p in ours], [p.texts for p in theirs],
                                      autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        pairs = list(zip(range(i1, i2), range(j1, j2)))
        for i, j in pairs:
            new_pages.append(_take(i, j, ours[i], theirs[j], raw_pages[i], manifest,
                                   workspace, shelf, written_assets, result))
        for i in range(i1 + len(pairs), i2):
            result.notes.append(f"page {i + 1}: removed in PowerPoint — dropped from the manifest")
        for j in range(j1 + len(pairs), j2):
            new_pages.append({"kind": "import", "deck": shelf, "page": j + 1,
                              "why": "PowerPoint で足された頁"})
            result.notes.append(f"page {j + 1} (edited): added in PowerPoint — imported as it is")

    text = manifest_path.read_text(encoding="utf-8")
    rewritten = _rewrite(text, new_pages)
    staged = workspace.root / f".{manifest_path.stem}.applying.toml"
    try:
        staged.write_text(rewritten, encoding="utf-8")
        _verify(workspace, staged, shelved, assets=manifest.assets)
        os.replace(staged, manifest_path)
    except Exception:
        for path in written_assets:
            path.unlink(missing_ok=True)
        raise
    finally:
        staged.unlink(missing_ok=True)
    # 手直し版を「最後に焼いた版」として覚える (= 次の build は、同じ中身で焼き直して上書きできる。
    # 開いている PowerPoint の file にはここで書かない)
    remember(edited)
    return result


def _take(i, j, old: _Page, new: _Page, raw: dict, manifest: Manifest, workspace,
          shelf: str, written: list[Path], result: Applied):
    """One page: unchanged, a text or picture change written into its entry, or the edited page."""
    entry = manifest.entries[i]
    page = f"page {i + 1}"
    if old.texts == new.texts and old.shape == new.shape and old.pictures == new.pictures:
        return i
    same_shape = old.shape == new.shape and len(old.pictures) == len(new.pictures)

    if same_shape and old.pictures == new.pictures and len(old.texts) == len(new.texts):
        changed = [(a, b) for a, b in zip(old.texts, new.texts) if a != b]
        updated = _text_into(dict(raw), entry.kind, changed)
        if updated is not None:
            result.notes.append(f"{page}: {len(changed)} words changed — written into the manifest")
            return updated

    if same_shape and old.texts == new.texts and raw.get("kind") in ("copy", "import"):
        names = []
        folder = workspace.assets / manifest.assets
        folder.mkdir(parents=True, exist_ok=True)
        for n, (data, original) in enumerate(zip(new.pictures, new.picture_names), start=1):
            name = f"{Path(manifest.out).stem}-p{i + 1}-{n}{Path(original).suffix.lower()}"
            (folder / name).write_bytes(data)
            written.append(folder / name)
            names.append(name)
        result.notes.append(f"{page}: pictures changed — {len(names)} taken into assets/{manifest.assets}/")
        return {**raw, "pictures": names}

    result.notes.append(
        f"{page}: changed in a way the manifest cannot say (position, size, format, or text in a "
        f"new place) — now imported as it was edited, from {shelf} page {j + 1}")
    return {"kind": "import", "deck": shelf, "page": j + 1, "why": "PowerPoint で整えた頁"}


def _text_into(raw: dict, kind: str, changed: list[tuple[str, str]]) -> dict | None:
    """The page's entry with each text change written in, or None when one cannot be."""
    if not changed:
        return None
    replace = [list(pair) for pair in raw.get("replace", [])]
    for before, after in changed:
        if kind == "declare" and _set_once(raw, before, after):
            continue
        for pair in replace:
            if pair[1] == before:  # 前の置換の行き先が直された → その対を直す
                pair[1] = after
                break
        else:
            if sum(1 for b, _a in changed if b == before) > 1:
                return None  # 同じ語が別々に直された (= 置換では書き分けられない)
            replace.append([before, after])
    if replace:
        raw["replace"] = replace
    return raw


def _set_once(raw: dict, before: str, after: str) -> bool:
    """Swap `before` for `after` where it is the whole of one value in the declaration, once."""
    found = []

    def walk(holder, key):
        value = holder[key]
        if isinstance(value, str) and value == before:
            found.append((holder, key))
        elif isinstance(value, list):
            for index in range(len(value)):
                walk(value, index)
        elif isinstance(value, dict):
            for inner in value:
                walk(value, inner)

    for key in raw:
        if key not in ("kind", "replace", "why", "recipe", "fill"):
            walk(raw, key)
    if len(found) != 1:
        return False
    holder, key = found[0]
    holder[key] = after
    return True


def _pages(deck: Path) -> list[_Page]:
    texts = [tuple(page.texts()) for page in read(deck)]
    order = Archive(deck.parent).order_of(deck)
    out = []
    with zipfile.ZipFile(deck) as archive:
        for number, slide in enumerate(order):
            xml = archive.read(f"ppt/slides/{slide}").decode("utf-8")
            shape = xml
            for pattern, repl in _UNSHAPE:
                shape = pattern.sub(repl, shape)
            try:
                rels = etree.fromstring(archive.read(f"ppt/slides/_rels/{slide}.rels"))
            except KeyError:
                rels = etree.fromstring(b"<Relationships/>")
            target = {r.get("Id"): r.get("Target", "") for r in rels}
            blobs, names = [], []
            for pic in pictures(etree.fromstring(xml.encode("utf-8"))):
                media = target.get(pic.find(".//a:blip", NS).get(f"{{{NS['r']}}}embed"), "")
                name = media.rsplit("/", 1)[-1]
                blobs.append(archive.read(f"ppt/media/{name}") if name else b"")
                names.append(name)
            out.append(_Page(texts[number], shape, tuple(blobs), tuple(names)))
    return out


def _manifest_for(workspace, deck: str) -> Path:
    found = []
    for path in workspace.manifests():
        try:
            if Manifest.load(path).out == deck:
                found.append(path)
        except ManifestError:
            continue
    if len(found) != 1:
        raise ApplyError(f"{'no' if not found else 'more than one'} manifest builds {deck}")
    return found[0]


def _rewrite(text: str, pages: list[dict | int]) -> str:
    """The manifest with its pages replaced by `pages` (= an int keeps that page's block as it was)."""
    lines = text.splitlines(keepends=True)
    heads = [n for n, line in enumerate(lines) if line.strip() == "[[pages]]"]
    blocks = []
    for index, start in enumerate(heads):
        end = next((n for n in range(start + 1, len(lines)) if TABLE_HEAD.match(lines[n])),
                   len(lines))
        blocks.append("".join(lines[start:end]))
    head = "".join(lines[:heads[0]]) if heads else text
    body = []
    for page in pages:
        if isinstance(page, int):
            block = blocks[page]
        else:
            block = "[[pages]]\n" + "".join(
                f"{toml_key(k)} = {dump(v)}\n" for k, v in
                sorted(page.items(), key=lambda kv: (kv[0] != "kind", 0))) + "\n"
        body.append(block if block.endswith("\n\n") or block.endswith("\n") else block + "\n")
    return head + "".join(body)


def _verify(workspace, staged: Path, edited: Path, *, assets: str) -> None:
    """Build the staged manifest and compare it with the edited deck, page by page.

    ⚠ 仮の manifest は名前が違うので、素材の folder は元の manifest のものを渡す
    (= 渡さないと、仮の名前の folder を探して絵が見つからない)。
    """
    from dataclasses import replace as with_

    from ..deck.build import build

    manifest = with_(Manifest.load(staged), assets=assets)
    with tempfile.TemporaryDirectory() as scratch:
        built = build(workspace, with_(manifest, out=str(Path(scratch) / "check.pptx")))
        mine, theirs = _pages(built), _pages(edited)
        if len(mine) != len(theirs):
            raise ApplyError(f"taken in, the deck would have {len(mine)} pages and the edited "
                             f"one has {len(theirs)}; nothing was written")
        for number, (a, b) in enumerate(zip(mine, theirs), start=1):
            if a.texts != b.texts:
                missing = [t for t in b.texts if t not in a.texts][:3]
                raise ApplyError(f"page {number} would not read as it was edited (missing: {missing}); "
                                 "nothing was written")
            if a.pictures != b.pictures:
                raise ApplyError(f"page {number} would not show the pictures it was edited to; "
                                 "nothing was written")
