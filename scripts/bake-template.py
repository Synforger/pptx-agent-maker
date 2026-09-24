"""Bake the real files the project template ships with (= a specimen and one picture).

テンプレートは本来**案件のもの**で、案件ごとの見た目と表紙がそこに入る。プロジェクトテンプレートが 1 枚だけ持つのは、
`init` した直後に 1 本焼けるようにするため ― 会社名もロゴも案件名も入っていない、ツールの
既定の見た目そのままの見本。案件は自分の `specimen.pptx` でこれを差し替える。

⚠ **見た目の真値は `layout/tokens.py` の 1 枚**で、この pptx はそこから焼いた派生物。
両者が一致していることは test が見ている (= 色や書体を変えたら `task specimen` で焼き直す)。

テンプレートはデッキの見た目そのもの ― 複製される頁 (= 表紙)、焼いたデッキのマスター
(= PowerPoint で開いて手で足した頁)、そして型で組んだ頁も、全部ここから見た目を取る。
案件は**この 1 枚を差し替えるだけ**でよい。
"""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.layout.page import Element, Fill, Text  # noqa: E402
from pptx_agent_maker.layout.tokens import DEFAULT, Theme  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

TEMPLATE = REPO / "src" / "pptx_agent_maker" / "templates" / "project"
DESTINATION = TEMPLATE / "specimen.pptx"
#: `example.toml` が指す絵。**プロジェクトテンプレートが 1 枚持つのは、init した直後に 1 本焼けるようにするため**
PICTURE = TEMPLATE / "assets" / "example" / "example.png"

#: 表紙の文言。差し替える前提なので、案件は `checks.stale_words` にこれを宣言しておく
TITLE = "案件名"
SUBTITLE = "第 N 回 進捗報告"

#: zip が書ける最も古い日時。**焼き直すたびに中身が変わると、見た目を変えていない回でも
#: 差分が出て、履歴からは何が動いたのか読めなくなる。**
EPOCH = (1980, 1, 1, 0, 0, 0)

#: テーマの色の枠 → ツールの色。PowerPoint 側の「デザイン」はこの 12 個しか持たない
SCHEME = (
    ("dk1", "ink"), ("lt1", "paper"), ("dk2", "muted"), ("lt2", "band"),
    ("accent1", "accent"), ("accent2", "good"), ("accent3", "bad"),
    ("accent4", "rule"), ("accent5", "box"), ("accent6", "muted"),
    ("hlink", "accent"), ("folHlink", "muted"),
)


def cover(theme: Theme) -> list[Element]:
    """The one page a specimen must have: a cover to be copied and reworded."""
    frame = theme.frame()
    upper, lower = frame.split_top(round(frame.height * 0.55))
    above, rule = upper.split_top(upper.height - theme.spacing.gap_s)
    title = above.split_top(above.height - theme.text_height(TITLE, above.width,
                                                             theme.type.title))[1]
    caption = lower.inset(top=theme.spacing.gap_m)
    return [
        Text("title", title, TITLE, theme.type.title, theme.palette.ink, bold=True),
        Fill("band", rule, theme.palette.accent),
        Text("caption", caption.split_top(theme.line_height(theme.type.heading))[0],
             SUBTITLE, theme.type.heading, theme.palette.muted),
    ]


def dress(deck: Path, theme: Theme) -> None:
    """Put the theme's own colours and typeface into the deck's master.

    python-pptx が起こすデッキは Office の既定の見た目を持つ。**そこを書き換えないと、
    PowerPoint で手で足した頁だけ別の書体と色で出る。**

    ⚠ **書き換えるのはテーマだけ** ― 頁の図形に直接書かれた色は動かない。案件のテンプレートは
    その案件の色で焼かれている (= 表紙の帯も) ので実害は無いが、既に焼いた見本を別の色へ
    「塗り替える」用途には使えない。
    """
    colours = "".join(
        f'<a:{slot}><a:srgbClr val="{getattr(theme.palette, name)}"/></a:{slot}>'
        for slot, name in SCHEME
    )
    scheme = f'<a:clrScheme name="Deck">{colours}</a:clrScheme>'

    with zipfile.ZipFile(deck) as archive:
        parts = {item.filename: archive.read(item.filename) for item in archive.infolist()}
        order = [item for item in archive.infolist()]

    theme_xml = parts["ppt/theme/theme1.xml"].decode("utf-8")
    theme_xml = re.sub(r"<a:clrScheme.*?</a:clrScheme>", scheme, theme_xml, count=1, flags=re.S)
    theme_xml = re.sub(r'<a:latin typeface="[^"]*"', f'<a:latin typeface="{theme.type.family}"',
                       theme_xml)
    theme_xml = re.sub(r'<a:ea typeface="[^"]*"', f'<a:ea typeface="{theme.type.family}"',
                       theme_xml)
    theme_xml = re.sub(r'<a:font script="Jpan" typeface="[^"]*"',
                       f'<a:font script="Jpan" typeface="{theme.type.family}"', theme_xml)
    parts["ppt/theme/theme1.xml"] = theme_xml.encode("utf-8")

    # ⚠ **寸法を変えても、紙の種類の申告は python-pptx の既定 (= 4:3) のまま残る。**
    # 頁を書き足す先のデッキでそれが食い違うと、PowerPoint の「スライドのサイズ」が
    # 実寸と別のことを言う。
    presentation = parts["ppt/presentation.xml"].decode("utf-8")
    kind = "screen16x9" if theme.slide.width * 9 == theme.slide.height * 16 else "custom"
    presentation = re.sub(r'(<p:sldSz[^>]*?) type="[^"]*"', rf'\1 type="{kind}"', presentation)
    parts["ppt/presentation.xml"] = presentation.encode("utf-8")

    with zipfile.ZipFile(deck, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in order:
            item.date_time = EPOCH
            archive.writestr(item, parts[item.filename])


def make(destination: Path = DESTINATION, theme: Theme = DEFAULT) -> Path:
    """Bake the specimen and return where it landed."""
    deck = new_deck(theme)
    add_page(deck, cover(theme), theme)
    baked = save(deck, destination.with_suffix(".tmp"))
    dress(baked, theme)
    shutil.move(baked, destination)
    return destination


def picture(destination: Path = PICTURE, theme: Theme = DEFAULT) -> Path:
    """Bake the one picture the example manifest points at.

    ⚠ **絵が無いと図の型は焼けない。**プロジェクトテンプレートが 1 枚持っていないと、init した直後の案件で
    最初に出るのが「素材が無い」になる。中身は無地で、絵の入る場所だと分かればよい。
    """
    from PIL import Image, ImageDraw

    width, height = 1600, 900
    image = Image.new("RGB", (width, height), f"#{theme.palette.band}")
    pen = ImageDraw.Draw(image)
    edge = round(width * 0.04)
    box = (edge, edge, width - edge, height - edge)
    pen.rectangle(box, outline=f"#{theme.palette.accent}", width=4)
    pen.line((box[0], box[1], box[2], box[3]), fill=f"#{theme.palette.rule}", width=3)
    pen.line((box[0], box[3], box[2], box[1]), fill=f"#{theme.palette.rule}", width=3)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    return destination


if __name__ == "__main__":
    print(f"baked {make()}")
    print(f"baked {picture()}")
