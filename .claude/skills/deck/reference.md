# 参照

## 版面の語彙 (= `layout/`)

| 呼び方 | 何 |
|---|---|
| `page.body` | 見出し・帯・出所を取った残り。ここを割って使う |
| `.columns(n or weights, gap)` / `.rows(...)` | 左右 / 上下に割る。割った枠は必ず親の中 |
| `.grid(rows, cols, gap)` | 行×列 |
| `.split_top(height, gap)` | 上から固定高を取り、残りを返す (= 表のように高さが中身で決まるもの) |
| `.inset(all / x / y / left …)` | 内側に縮める |
| `.fit(aspect)` | その縦横比で最大、中央寄せ (= 絵はこれでしか置けない) |

`DEFAULT.spacing.gap_s / gap_m / gap_l`、`DEFAULT.palette.ink / muted / accent / good / bad /
band / box / rule`、`DEFAULT.type.title / heading / body / caption`、`DEFAULT.table_height(rows)`。

## manifest

```toml
specimen = "base/specimen.pptx"
out = "w1.pptx"

[[pages]]
kind = "copy"        # 型見本の N 頁目
page = 1
replace = [["旧", "新"]]

[[pages]]
kind = "import"      # 前のデッキの N 頁目
deck = "output/w0.pptx"
page = 12

[[pages]]
kind = "declare"     # pages/<module>.py の build(workspace)
module = "latency"
```

## 検査

`build` は最後に 5 つを回す ― 版面外 / 文字の下限 / 表の空セル / 内部 file 名 /
型見本の語の残り。`stale_words` は案件の `workspace.toml` に書く。

```toml
[checks]
stale_words = ["W3 の値", "旧版"]
```
