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

**A page picks a type and fills it in.** There is no call that takes a coordinate — not in the
manifest, and not inside the types either.

```toml
[[pages]]
kind = "declare"
type = "figure"
kicker = "02 | results"
title = "Where the wait comes from"
condition = "Same request mix, three builds, one build per column"
cards = [["Cold start", "..."], ["Warm cache", "..."]]
figure = "latency.png"
caption = "p95 by endpoint"
table = [["build", "p95"], ["A", "120 ms"], ["B", "340 ms"]]
note = "blue = within budget / red = over"
conclusion = "Most of the wait is the first read after a deploy"
footer = "measured on the load test of the day"
```

The order of a page is settled and never varies: **title → condition → cards → body → table →
reading → conclusion → footer.** A band left unwritten is simply not taken. The type decides one
thing — what goes in the body — and there are seven of them (`figure`, `figures`, `figure_grid`,
`flow`, `cards`, `board`, `agenda`). Cards, a table and the reading can be added to any of them.

Naming a few positions and asking people to use them does not hold: the previous generation did
exactly that, and values with no name piled up right beside the ones that had them.

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

The toolkit is here. Manifests, assets and built decks live in a workspace that this repo only
points at. Data cannot enter a commit, so it cannot enter a push.

## Three layers

- **the toolkit** — this repository: the vocabulary of the page (seven types) and the machinery.
  Installed **once per machine**
- **the template** — `src/pptx_agent_maker/templates/project/`: where a project starts (its look,
  an example manifest, and its entry point). It **ships with the toolkit**, so an installed
  copy can lay down a project too
- **a project** — what `init` lays down: data, declarations and a look. **The toolkit is not in it**

**A new type is added to the toolkit**, and every project has it at once: there is nothing to
distribute. What a project owns is its look and the order of its pages, and those differ by project.

A project stands on its own — its `Taskfile.yml` is the door to the toolkit.

```bash
pipx install .                          # install the toolkit, once
pptx-agent-maker init <project-dir> --specimen <look.pptx>
cd <project-dir> && task build -- example
```

## The look belongs to the project, the layout to the toolkit

A project sets its own **typeface and colours** in `[theme]` in its `workspace.toml`, and pages
built from a type come out in them. **Margins, type sizes and spacing cannot be set**: the same
kind of page keeping the same shape from one round to the next is worth more, and the generation
that left that open produced a different page every week.

The template ships with **one specimen, baked in the toolkit's own look**, so a project can build
a deck the moment it is created. To use a project's own look, **replace that one file** — copied
pages, pages built from a type and the master a person sees in PowerPoint all take it from there.
`[theme]` is the exception laid on top, for when a specimen's palette does not line up with what
the toolkit means by each colour; only what is written there is overridden.

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
templates/     the skeleton a deck project is created from (it ships with a specimen)
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

Every layer is in place and covered: declaring a page, writing it to pptx, copying a specimen,
importing a page from an earlier deck, building a deck from one manifest, reading the built file
back through five checks, protecting a hand edit, and watching the result in a browser.

## License

Apache-2.0 — see [LICENSE](LICENSE). The bundled preview under `preview/` is part of this
repository and ships under the same license.
