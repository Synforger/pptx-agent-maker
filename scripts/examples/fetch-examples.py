#!/usr/bin/env python3
"""Gather the decks people ranked best, for an agent to look at before it plans a deck.

作法 (= deck skill の craft.md) の「作る前に、場面の近い見本を見る」が指す集まりを、機械ごとに
揃える。repo には入れない (= 他者のデータ)。置き場の既定
(= 器の根 `AGENT_PLATFORM_ROOT` が在る時は `<根>/references/pptx-agent-maker/examples/`):

    ~/.local/share/pptx-agent-maker/examples/
    ├── INDEX.md            # 場面ごとの一覧と見方 (= agent が最初に開く 1 枚)
    ├── slides-align/       # 人が 1 番に選んだ資料 (= Slides-Align、MIT、研究用)
    │   └── <場面>/<題材>/1-<道具>/page-NN.jpg と page-NN.md
    └── albums/             # プレビューで見る束 (= `.album`、絵は slides-align/ を指すだけ)
        ├── scenes/<場面>/NN-<1 頁目の題>.album   # 資料 1 本 = 束 1 本
        └── forms/<頁の形>.album                  # 形 1 つ = 束 1 本 (= 語で拾った候補)

    python3 scripts/examples/fetch-examples.py [--to DIR] [--no-fetch]

束をプレビューの欄に出すには、プレビューの設定 file (= 既定 `~/.config/pptx-agent-maker/preview.toml`、
器の根が在る時は `<根>/config/pptx-agent-maker/preview.toml`) に場面と形の folder を
`[[folder]]` で足す (= 書く行は `--no-fetch` の最後に出る)。

⚠ **取るのは 1 位だけ。**agent が 1 回に開くのは 2〜3 本で、1 位 (= 題材ごとに 1 本、187 本) で足りる。
⚠ **途中で落ちても続きから。**取れた file は飛ばすので、打ち直せば残りだけを取る。配る側で取れない
file は飛ばして数え、一覧の末尾に出す (= 1 file のために全体を止めない)。
⚠ **形の束は語で拾った候補。**頁の文字の抜き出し (= 「3. Visual Interpretation」) の太字の見出しを語で
引くので、外れも混ざり、見落としもある。場面の束は資料をそのまま並べるので外れない。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from pptx_agent_maker.project.files.places import default_places_file
from pptx_live_preview.platform_root import tool_folder

ALIGN = "https://huggingface.co/datasets/Yqy6/Slides-Align"
ALIGN_API = "https://huggingface.co/api/datasets/Yqy6/Slides-Align/tree/main/"
#: 頁の絵の長辺 (= agent が読む時に縮める大きさ。原寸の 3000px は容量の払い損)
EDGE = 1600
#: 同時に取りに行く数 (= 配る側に優しく、回線を詰めない)
WORKERS = 8
#: 順位の file の製品名と、配る側の folder 名の違い (= 綴りが揃っていない)
FOLDER = {"Skywork-Banana": "Skyworks-Banana", "Skywork": "Skyworks"}
#: 場面の通り名 (= INDEX の見出し)
SCENES = {
    "work_report": "業務の報告",
    "business_plan": "事業計画",
    "product_launch": "製品の発表",
    "course_preparation": "授業の資料",
    "topic_introduction": "題材の紹介",
    "brand_promote": "ブランドの宣伝",
    "personal_statement": "自己紹介",
}

#: 頁の形と、それを拾う語 (= 抜き出しの「3. Visual Interpretation」の太字の見出しに当てる。小文字で)。
#: `text` は見出しでなく節の本文に当てる (= 大きな数字は見出しに名前が出ない)。`not` に当たる見出しは外す
FORMS = {
    "大きな数字": {"text": r"\b(?:large|big|oversized|giant|huge|massive|enlarged)\b[\w ,-]{0,20}?\b"
                          r"(?:numerals?|numbers?|percentages?|figures?|digits?|statistics?)\b"
                          r"|\bkey (?:metric|statistic|figure)s?\b",
                  "not": r"slide number|page number"},
    "発言": {"label": r"\bquot(?:e|es|ation|ations)\b|\btestimonial"},
    "写真や図に線で名前": {"label": r"\bcallout (?:arrow|line)s?\b|\bannotations?\b|\bleader lines?\b"
                                 r"|\barrows and labels\b|\blabel(?:l)?ed (?:diagram|illustration|photo|image)"},
    "木の図": {"label": r"\b(?:tree|branching) (?:diagram|structure|chart|graph|layout)|\bdecision tree"
                       r"|\bhierarch\w* (?:diagram|chart|structure|tree|layout|flow)|\borg(?:anizational|anisational)? ?chart"
                       r"|\bmind ?map"},
    "輪の図": {"label": r"\bcircular (?:flow |arrow )?diagram|\bcycle (?:diagram|graphic)|\b\d+-stage cycle"
                       r"|\bloop diagram|\bcircular graphic"},
    "コードの枠": {"label": r"\bcode\b|\bterminal\b", "not": r"\b(?:qr|colou?r|zip|dress|post(?:al)?) code\b"},
    "円の重なり": {"label": r"\bvenn\b|\boverlapping circles?\b"},
    "地図": {"label": r"\bmap\b",
             "not": r"background|icon|faint|watermark|\b(?:mind|road|heat|empathy|journey|site|concept) ?map"},
    "数式": {"label": r"\bequations?\b|\bformulas?\b|\bmathematical\b"},
}

GUIDE = """\
# 良い資料の見本 (= 作る前に見る)

構成案を書く前に、場面の近い資料を 2〜3 本開いて、**話の並べ方** (= 何枚で、どの順で) と
**1 頁の見え方** (= 主役の図、字の量、余白、目を集める所) を見る。作法の真値は道具の deck skill の
`craft.md` で、ここは「人が 1 番に選んだ実物」を見るための置き場。

## 何が在るか

`slides-align/<場面>/<題材>/1-<道具>/` に、同じ依頼から 9 つの AI 道具が作った資料のうち、人が 1 番に
選んだ物 (= 頁の絵 `page-NN.jpg` と、頁ごとの文字の抜き出し `page-NN.md`)。出所は Slides-Align
(= MIT、研究用と明記)。外に出さない。

## 見方

- **真似するのは、構成・量・配置**。⚠ 1 番の多くは頁を丸ごと画像生成で描いた物で、字も絵に焼き込まれ、
  絵の中の綴りが崩れている所がある ― 絵に字を焼く作り方と飾りは真似しない (= 作法の「概念図と工程図は
  図形で組み、画像に文字を焼かない」)
- 1 頁だけを見ず、資料を頭から順に見る (= `page-NN.md` の題を順に読むと、話の筋だけが追える)

## プレビューで見る

常駐のプレビューの欄で「見本 · <場面>」を選ぶと、その場面の資料が 1 本ずつタブに並ぶ (= `albums/scenes/`)。
「見本 · 頁の形」は、形ごとの頁を集めた束 (= `albums/forms/`、大きな数字・発言・木の図・輪の図・地図ほか)。
⚠ 形の束は、頁の文字の抜き出しを語で拾った候補で、外れも混ざる。頁の下の注記に、元の資料と頁と、
当たった語が出る。
"""


def get(url: str, tries: int = 4) -> bytes:
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise
            time.sleep(2 ** attempt)
        except OSError:
            time.sleep(2 ** attempt)
    raise OSError(f"gave up on {url}")


def tree(path: str) -> list[dict] | None:
    try:
        return json.loads(get(ALIGN_API + urllib.parse.quote(path) + "?recursive=true"))
    except urllib.error.HTTPError:
        return None  # 順位は在るが、配る側に folder が無い


def slug(text: str) -> str:
    return re.sub(r"[^\w.-]+", "_", text).strip("_")[:60]


def title_of(markdown: str) -> str:
    # 抜き出しの書き方が 2 通りある (= `**Title:**` と `**Title**:`)
    found = re.search(r"\*\*Title(?::\*\*|\*\*:)\s*(.+)", markdown)
    return found.group(1).strip() if found else ""


def fetch_deck(entry: dict, to: Path) -> dict:
    """One ranked deck: its pages as JPEG and each page's text, skipping what will not come."""
    folder = f'{FOLDER.get(entry["product"], entry["product"])}/{entry["difficulty"]}/{entry["topic"]}'
    files = tree(folder)
    if files is None:
        return {**entry, "missing": True}
    deck = to / entry["difficulty"] / slug(entry["topic"]) / f'{entry["rank"]}-{entry["product"]}'
    deck.mkdir(parents=True, exist_ok=True)
    titles, failed = [], []
    for kind, suffix in (("slide_images", ".png"), ("slide_contents", ".md")):
        names = sorted(f["path"] for f in files
                       if f["type"] == "file" and f"/{kind}/" in f["path"] and f["path"].endswith(suffix))
        for number, path in enumerate(names, 1):
            url = f"{ALIGN}/resolve/main/{urllib.parse.quote(path)}"
            out = deck / f"page-{number:02d}{'.jpg' if kind == 'slide_images' else '.md'}"
            try:
                if not out.exists() and kind == "slide_images":
                    image = Image.open(io.BytesIO(get(url))).convert("RGB")
                    image.thumbnail((EDGE, EDGE))
                    image.save(out, "JPEG", quality=85)
                elif not out.exists():
                    out.write_bytes(get(url))
            except (OSError, ValueError) as error:  # 取れない 1 file で資料ごと捨てない
                failed.append(f"{path}: {error}")
                continue
            if kind == "slide_contents":
                titles.append(title_of(out.read_text(encoding="utf-8", errors="replace")))
    pages = len(list(deck.glob("page-*.jpg")))
    return {**entry, "path": str(deck.relative_to(to.parent)), "pages": pages, "titles": titles,
            "failed": failed}


def slides_align(root: Path) -> list[dict]:
    to = root / "slides-align"
    to.mkdir(parents=True, exist_ok=True)
    rankings = json.loads(get(f"{ALIGN}/resolve/main/Slides-Align.json"))["results"]
    wanted = [r for r in rankings if r["rank"] == 1]
    done = 0

    def one(entry):
        nonlocal done
        result = fetch_deck(entry, to)
        done += 1
        if done % 20 == 0 or done == len(wanted):
            print(f"  slides-align: {done}/{len(wanted)} decks", flush=True)
        return result

    with ThreadPoolExecutor(WORKERS) as pool:
        decks = list(pool.map(one, wanted))
    (to / "decks.json").write_text(json.dumps(decks, ensure_ascii=False, indent=1), encoding="utf-8")
    return decks


def index(root: Path, decks: list[dict]) -> None:
    lines = [GUIDE, "## 場面ごとの一覧\n"]
    by_scene = defaultdict(list)
    for deck in decks:
        if not deck.get("missing"):
            by_scene[deck["difficulty"]].append(deck)
    for scene, name in SCENES.items():
        rows = sorted(by_scene.get(scene, []), key=lambda d: d["topic"])
        if not rows:
            continue
        lines += [f"### {name} (`{scene}`、{len(rows)} 本)\n", "| 題材 | 道具 | 頁 | 1 頁目の題 | folder |",
                  "|---|---|---|---|---|"]
        for d in rows:
            first = (d["titles"][0] if d["titles"] else "").replace("|", "/")[:70]
            lines.append(f'| {d["topic"]} | {d["product"]} | {d["pages"]} | {first} | `{d["path"]}` |')
        lines.append("")
    missing = sum(1 for d in decks if d.get("missing"))
    failed = sum(len(d.get("failed", [])) for d in decks)
    if missing or failed:
        lines.append(f"配る側に folder が無く取れなかった資料: {missing} 本 / 取れなかった file: {failed} 個 "
                     "(= `slides-align/decks.json` の `failed`。打ち直せば取り直す)\n")
    (root / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def visual_labels(markdown: str) -> tuple[list[str], str]:
    """The bold headings of a page's "Visual Interpretation" section, and the section itself (both lowercased)."""
    found = re.search(r"## 3\. Visual Interpretation(.*?)(?:\n## |\Z)", markdown, re.S)
    if not found:
        return [], ""
    section = found.group(1).lower()
    labels = [label.strip(" :") for label in re.findall(r"^\s*[-*]\s+\*\*([^*]+)\*\*", section, re.M)]
    return labels, section


def form_of(markdown: str) -> dict[str, str]:
    """Form → the words that picked this page for it (= a guess from the words, not a judgement)."""
    labels, section = visual_labels(markdown)
    picked = {}
    for form, rule in FORMS.items():
        unwanted = re.compile(rule["not"]) if "not" in rule else None
        if "label" in rule:
            hit = next((label for label in labels
                        if re.search(rule["label"], label) and not (unwanted and unwanted.search(label))), None)
        else:
            found = re.search(rule["text"], section)
            hit = found.group(0) if found and not (unwanted and unwanted.search(found.group(0))) else None
        if hit:
            picked[form] = hit
    return picked


def albums(root: Path, decks: list[dict]) -> list[tuple[str, Path]]:
    """Write the albums the preview shows: one per deck under each scene, one per form. → (name, folder) to offer."""
    out = root / "albums"
    if out.exists():
        shutil.rmtree(out)  # 書き直す (= 束は slides-align/ から毎回作る写しで、手で足す物は置かない)
    by_form: dict[str, list[str]] = defaultdict(list)
    offers = []
    for scene, scene_name in SCENES.items():
        rows = sorted((d for d in decks if not d.get("missing") and d["difficulty"] == scene),
                      key=lambda d: d["topic"])
        if not rows:
            continue
        folder = out / "scenes" / scene
        folder.mkdir(parents=True)
        offers.append((f"見本 · {scene_name}", folder))
        for number, deck in enumerate(rows, 1):
            path = root / deck["path"]
            title = (deck["titles"][0] if deck["titles"] else "") or deck["topic"]
            pages = sorted(path.glob("page-*.jpg"))
            lines = []
            for page in pages:
                lines += [f"# {scene_name} · {title} · {page.stem[5:]}/{len(pages):02d} 頁",
                          os.path.relpath(page, folder)]
                text = page.with_suffix(".md")
                if text.is_file():
                    for form, words in form_of(text.read_text(encoding="utf-8", errors="replace")).items():
                        by_form[form] += [f"# {scene_name} · {title} · {page.stem[5:]} 頁目",
                                          f"# 拾った語: {words}", str(page)]
            # ⚠ 番号を頭に付ける (= 題を縮めた名前だけだと、同じ書き出しの資料が上書きし合う)
            name = f"{number:02d}-{slug(title)[:40]}.album"
            (folder / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    forms = out / "forms"
    forms.mkdir(parents=True)
    for form in FORMS:
        listed = by_form.get(form, [])
        if listed:
            lines = [line if line.startswith("#") else os.path.relpath(line, forms) for line in listed]
            (forms / f"{form}.album").write_text("\n".join(lines) + "\n", encoding="utf-8")
    offers.append(("見本 · 頁の形", forms))
    return offers


def default_examples_folder() -> Path:
    """Where the collection is gathered: under the platform root when one is given, else ~/.local/share."""
    references = tool_folder("references")
    if references is not None:
        return references / "examples"
    return Path.home() / ".local" / "share" / "pptx-agent-maker" / "examples"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--to", type=Path, default=None,
                        help="where to gather (default: references/pptx-agent-maker/examples under "
                             "$AGENT_PLATFORM_ROOT when set, else ~/.local/share/pptx-agent-maker/examples)")
    parser.add_argument("--no-fetch", action="store_true",
                        help="rebuild the index and the albums from what is already gathered")
    args = parser.parse_args(argv)
    started = time.monotonic()
    root = (args.to or default_examples_folder()).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    if args.no_fetch:
        decks = json.loads((root / "slides-align" / "decks.json").read_text(encoding="utf-8"))
    else:
        print("slides-align: fetching the decks ranked first", flush=True)
        decks = slides_align(root)
    index(root, decks)
    offers = albums(root, decks)
    got = [d for d in decks if not d.get("missing")]
    failed = sum(len(d.get("failed", [])) for d in decks)
    forms = {p.stem: len([line for line in p.read_text(encoding="utf-8").splitlines() if not line.startswith("#")])
             for p in sorted((root / "albums" / "forms").glob("*.album"))}
    print(f"{len(got)} decks ({sum(d['pages'] for d in got)} pages), {len(decks) - len(got)} not offered, "
          f"{failed} files that would not come; index at {root / 'INDEX.md'}")
    print("forms (pages picked by their words): " + ", ".join(f"{k} {v}" for k, v in forms.items()))
    print(f"to see them in the preview, add to {default_places_file()}:\n")
    for name, folder in offers:
        print(f'[[folder]]\nname = "{name}"\npath = "{folder}"\n')
    print(f"done in {time.monotonic() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
