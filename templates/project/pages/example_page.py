"""この案件の頁の見本。

版面の語彙 (= 帯・カード・図・表) は道具が持ち、**何をどう並べるかだけ**をここに書く。
座標は書けない (= 書く口が無い)。
"""

from pptx_agent_maker import DEFAULT, Page


def build(workspace):
    """Return a Page. The manifest decides where in the deck it lands."""
    page = Page(
        "見本の頁",
        kicker="01 | 見本",
        condition="ここに、その頁で固定した条件を 1 行",
        conclusion="ここに、読み手に持ち帰ってほしい 1 行",
        footer="出所 (= どの run のどの表から来たか)",
    )
    left, right = page.body.columns([2, 1], gap=DEFAULT.spacing.gap_m)
    page.figure(left, workspace.asset("example.png"), 16 / 9, caption="図の読み方を 1 行")

    rows = [["列", "値"], ["A", "1"], ["B", "2"]]
    table, note = right.split_top(DEFAULT.table_height(len(rows)), gap=DEFAULT.spacing.gap_s)
    page.table(table, rows)
    page.note(note, "表の読み方を 1 行")
    return page
