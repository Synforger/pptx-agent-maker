# 参照

## 案件を建てる

```bash
pptx-agent-maker init <案件のフォルダ> --specimen <型見本.pptx or それを置いた folder>
```

⚠ **見た目は建てるときに決める** (= あとから `specimen.pptx` を手で置き換えると、
忘れた回だけ顔が変わる)。folder を渡すと `specimen.pptx` と隣の `workspace.toml`
(= 色の表) を一緒に持ってくる。

## manifest

```toml
specimen = "specimen.pptx"     # 予約名。案件の見た目
out = "w1.pptx"                # マニフェストの隣に焼かれる
assets = "w1"                  # 省略すると、この file の名前が素材の folder 名

[[pages]]
kind = "copy"                  # 型見本の N 頁目を複製して文言を差し替える
page = 1
replace = [["旧", "新"]]

[[pages]]
kind = "import"                # 前のデッキの N 頁目を、手を入れたまま持ってくる
deck = "w0.pptx"
page = 12

[[pages]]
kind = "declare"               # 型で組む
type = "figure"
title = "…"
```

⚠ **`why` は 1 行の覚え書き** (= 200 字、日付を書くと拒まれる)。改訂の履歴は git log が持つ。

## 型 (= 本体に何を置くか)

| 型 | 要るもの | この型だけが読むもの | 本体 |
|---|---|---|---|
| `figure` | `figure` | `caption` | 絵を 1 枚、縦横比のまま最大で |
| `figures` | `figures` | ― | 絵を横に並べる (= 説明は絵ごとに `["a.png", "説明"]`) |
| `figure_grid` | `figures` | `columns` | 絵を格子に並べる |
| `flow` | `stages` | ― | 段を左から右へ、あいだに印 |
| `cards` | ― | ― | 札だけの頁 (= 図が要らない骨格) |
| `board` | `table` | ― | 表が主役の頁 (= 同上) |
| `agenda` | `buckets` | ― | 章立て (= 同上) |

## どの型にも添えられるもの

`cards` / `table` / `note` / `points`

⚠ **その型が読まないキーは拒まれる** (= 書いたつもりで頁に無い、を作らない)。

## 枠まわり (= どの頁も同じ順)

`kicker` / `title` / `condition` / `conclusion` / `footer` / `replace` / `highlight`

## 見た目 (= `workspace.toml`)

```toml
[theme]
font = "Arial"

[theme.palette]
ink = "3F3F3F"      # 本文
accent = "0092D1"   # 読みを示す色 (= 表の見出しもここ)
band = "EAF0F8"     # 条件の帯
```

⚠ **ふつうは書かない** ― 見た目は `specimen.pptx` から読まれる。ここに書くのは、型見本の
配色が道具の語彙と合わないときだけ。差し替えられるのは**書体と色だけ**で、
余白・級数・間隔は道具が持つ。

## 検査

`build` は最後に 6 つを回す ― 版面外 / **重なり** / 文字の下限 / 表の空セル /
内部 file 名 / 型見本の語の残り。`stale_words` は案件の `workspace.toml` に書く。

```toml
[checks]
stale_words = ["案件名", "第 N 回"]
```
