---
name: deck
description: Build or change a slide deck with pptx-agent-maker. Use when asked to make, edit, rebuild or review a .pptx deck in a project that has a workspace.toml — creating pages, copying from a specimen, importing a page from an earlier deck, checking a built deck, or folding a person's hand edits back in.
---

# Building a deck

**道具はこの repo、案件は外。**案件を見つける口は `workspace.toml` 1 枚で、それ以外に外の
path を書かない。

## 順番

1. **既に在るものを見る** ― `python3 -m pptx_agent_maker show <project>` と、
   その案件の `manifests/` と `pages/`。**同じ役割の頁が過去に在れば、それを複製するか輸入する**
2. **manifest を書く / 直す** ― 並びの真値はここ 1 枚。頁の作り方は 3 つだけ
   (`copy` / `import` / `declare`)
3. **組む** ― `python3 -m pptx_agent_maker build <project> <manifest>`
4. **焼いて見る** ― `python3 -m pptx_agent_maker preview <project>`。
   ⚠ **検査が通っても、読みやすさは座標に出ない。**目で見るまで終わりでない
5. **人が直したら取り込む** ― `python3 -m pptx_agent_maker review <project> <deck>` で
   差分を出し、置換の対を manifest に写す

## 頁を新しく書くとき

案件の `pages/<name>.py` に `build(workspace) -> Page` を書く。**座標を渡す口は無い** ―
版面を割ることしかできない。

```python
page = Page(title, kicker=..., condition=..., conclusion=..., footer=...)
left, right = page.body.columns([2, 1], gap=DEFAULT.spacing.gap_m)
figure_area, cards = left.rows([3, 2], gap=DEFAULT.spacing.gap_m)
page.figure(figure_area, workspace.asset("x.png"), 16 / 9, caption="…")
table, note = right.split_top(DEFAULT.table_height(len(rows)), gap=DEFAULT.spacing.gap_s)
page.table(table, rows, highlight={(1, 1): DEFAULT.palette.good})
page.note(note, "…")
```

## 組めないもの (= 直そうとせず、形を変える)

| 拒まれるもの | なぜ |
|---|---|
| 図解を 1 つも持たない頁 | 表と文章だけの頁は、読み手が使えない |
| 表の空セル | 値が無いなら「―」。空欄は埋め忘れと見分けが付かない |
| 10pt を割る文字 | 席から読めない |
| 枠に入らない表 | PowerPoint は表を縮めず枠を伸ばす。頁から溢れる |
| 手編集された deck への上書き | 人の直しは退避してから、`review` で取り込む |

## やらないこと

- **寸法・色・文字を頁が決めない** ― `DEFAULT` の token を参照する。同じ役割が毎週同じ形で
  出ることが、週をまたいだ比較の前提
- **案件のものを道具側に置かない** ― 結果を並べる頁のように、並べ方が案件に固有のものは `pages/`
- **1 往復 1 修正を繰り返さない** ― 焼く前に、その頁の文言と寸法を決め切る
