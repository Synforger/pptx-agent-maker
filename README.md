# pptx-agent-maker

> Build slide decks by **declaring structure, not coordinates** — so the same kind of page comes
> out the same way every week, and an agent writing one cannot put anything outside the page.

## Why

Decks built week after week from the same skeleton drift. Pages that should look identical are
written again from scratch, the layout wanders, and a one-line fix costs a rebuild-and-look round
trip. Looking back over a long-running weekly deck, the pattern was always the same: a page copied
whole one week, rewritten from nothing a few weeks later, and a pile of page scripts that were
never rendered at all.

Every one of those pages placed its shapes by writing EMU coordinates. The complaint was never
"this is wrong" — it was *"I hate that the design keeps changing"* and *"a new arrangement is
cognitive load; the same shape is what lets me compare across weeks."*

## What is different here

**A page is declared by dividing its frame.** There is no call that takes a coordinate.

```python
page = Page("Where the wait comes from",
            kicker="02 | results",
            condition="Same request mix, three builds, one build per column",
            conclusion="Most of the wait is the first read after a deploy",
            footer="measured on the load test of the day")

left, right = page.body.columns([2, 1], gap=DEFAULT.spacing.gap_m)
figure_area, cards = left.rows([3, 2], gap=DEFAULT.spacing.gap_m)

page.figure(figure_area, "latency.png", 16 / 9, caption="p95 by endpoint")
page.boxes(cards, [("Cold start", "..."), ("Warm cache", "...")])
table, note = right.split_top(DEFAULT.table_height(4), gap=DEFAULT.spacing.gap_s)
page.table(table, rows, highlight={(1, 1): DEFAULT.palette.good})
page.note(note, "blue = within budget / red = over")
```

Four things then hold **by construction**, not by a checker run afterwards:

- **Nothing leaves the page.** A rectangle can only be divided, and a division stays inside its parent.
- **Siblings never overlap.** They are cut from the same area.
- **The same declaration gives the same coordinates.** A page built twice is the same page.
- **Images keep their aspect ratio.** `fit` is the only way one is placed.

And four things are refused outright, because no one managed to hold them by discipline:

- a page with **no figure** (= prose and tables only)
- an **empty table cell** (write a dash; a blank reads as a value nobody filled in)
- type **below the floor** (10pt on the slide)
- a **table taller than the space given** — PowerPoint grows the frame instead of shrinking the
  table, so the page silently overflows. The height a table will occupy is known before it is placed.

## The other rule: a deck project lives outside this repo

The toolkit is here. Manifests, assets, page scripts and built decks live in a workspace that this
repo only points at. Data cannot enter a commit, so it cannot enter a push.

## Try it

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
task test
```

## Layout of this repository

```
src/pptx_agent_maker/
├── layout/    dividing the frame — the only place coordinates exist
├── write/     turning a declared page into a file
├── deck/      copying a specimen page, importing one from an earlier deck
├── checks/    reading a built deck back, one check per file
├── review/    keeping a person's edit, and showing it as words
└── project/   pointing at a deck project that lives outside this repo
templates/     the skeleton a deck project is created from
preview/       the live preview, vendored with its own history (git subtree)
```

A project is created outside the repo and the toolkit is pointed at it:

```bash
python3 -m pptx_agent_maker init <project-dir>    # lay down the project skeleton
python3 -m pptx_agent_maker build <project-dir> w1   # build a deck from a manifest
python3 -m pptx_agent_maker check <project-dir> w1   # read the built file back
python3 -m pptx_agent_maker preview <project-dir>    # watch output/ in a browser
python3 -m pptx_agent_maker review <project-dir> w1  # what a person changed, as pairs
```

A `workspace.toml` that points inside this repository is refused, and a missing asset stops the
build rather than being passed on as a path.

Files are grouped by role, not by type: a directory should say what is in it before you open
anything. `preview/` keeps its own README, tests and Taskfile, and is updated with
`git subtree pull`.

## Status

The declarative layer, the theme tokens and the pptx writer work end to end: a page declared in
Python renders, converts and reads correctly, and the preview is now in the same repository.
Next: the workspace file that points at a deck project, the project skeleton that lives outside
this repo, and the layers worth porting from the previous generation (specimen copying, importing
a page from an earlier deck).
