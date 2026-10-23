---
name: making-decks
description: Make, change or check a slide deck (.pptx) with pptx-agent-maker, or edit a .pptx the toolkit did not build. Use when asked to make slides, plan the pages of a deck, fix how a deck looks, or when PowerPoint offers to repair a file.
---

# Making a deck

Pick the route first. Everything below the table is for the third route; the first two are
carried by files that already exist, so this skill names them and does not copy them.

| Situation | Where the instructions are |
|---|---|
| The deck lives in a project (a folder with a `workspace.toml`) | The project's own `deck` skill, in `<project>/.claude/skills/deck/`. It is the mechanism: the tasks, the manifest, the page types |
| There is no project yet | `pptx-agent-maker init <project-dir> --specimen <look>` (the `.pptx` the look comes from, or a folder holding one), then the project's `deck` skill. A deck in an organisation's look is built this way, not by editing XML by hand |
| A `.pptx` the toolkit did not build, or one you may not run the toolkit on | [Editing a pptx without the toolkit](#editing-a-pptx-without-the-toolkit) below |

## Read the craft file before designing a page

The steps of making a deck, in the order they must not be skipped, open the project's `deck` skill.
How a deck should read — the order of the story, how a page looks, figures and charts, how real
material and numbers are handled, wording and facts, how to work, what a report, a proposal and a
deck for an outside party each need, and which type to use for which page — is one file, `craft.md`.
Types and checks can only guard coordinates and shapes; the rest is the author's.

- In a project, read the `craft.md` that sits beside the project's `deck` skill.
  `task refresh` replaces a stale copy
- Outside a project, read the one this plugin ships:
  `${CLAUDE_PLUGIN_ROOT}/src/pptx_agent_maker/templates/project/.claude/skills/deck/craft.md`

## Where a new rule goes

- **A rule for any deck** goes into the toolkit's `craft.md`, as a pull request to this repository.
  Do not keep a copy in a project or in your own notes: a copy fixes the deck that was sent back and
  nothing after it
- A rule for one organisation's decks goes into that organisation's template notes
- A rule for one project goes into that project

## When the toolkit cannot make what the page needs

First suspect the amount of text and the way it is arranged, not the toolkit. A shape that is
missing and would be used again goes to the toolkit as a request that describes the general shape
(a new type or piece); a one-off shape is written as a part in the project's `recipes.toml`. The
steps for adding a type are in `docs/reference/adding-a-type.ja.md`.

## Editing a pptx without the toolkit

Use this only when the toolkit cannot be the route. When PowerPoint offers to repair a deck the
toolkit built, do not follow this section: the method for finding the cause is in `craft.md`.

**Mechanism**

- Write the result as a **new version** of the file. Leave the previous `.pptx` and `.pdf` as they are,
  and never write over a file a person has open in PowerPoint
- Edit through Anthropic's `pptx` skill rather than writing XML by hand
  (<https://github.com/anthropics/skills/tree/main/skills/pptx>): `unpack.py` and
  `pack.py` around the edit, `add_slide.py` to duplicate a slide, `clean.py` to drop what nothing
  refers to, `thumbnail.py` for an overview. Its scripts import `defusedxml`, so run them with a
  Python that has it installed
- To create a deck with no template, use `pptxgenjs` (`npm i pptxgenjs`)
- Name a font that has the characters. Without one, LibreOffice draws Japanese and other non-Latin
  text as blanks when it renders the check images (on macOS, `Hiragino Sans` works)
- Keep a deck's review PDF beside the deck, not in a shared or synced folder, so a client's deck
  does not leave the place it belongs

**Removing and extracting slides**

- To show one slide, narrow `<p:sldIdLst>` in `presentation.xml` to that slide's `sldId`; the others
  stay in the file but are not drawn
- To **delete** a slide, remove the whole part: its entry in `sldIdLst`, its relationship, its
  `Content_Types` override and the slide file. A slide that is only dropped from `sldIdLst` is an
  orphan, and orphans are one cause of the repair prompt
- A shape with no text carries a `txBody` holding only `<a:endParaRPr>`. An empty
  `<a:r><a:t></a:t></a:r>` triggers the repair prompt

**Check after every pack. Both are required**

1. **Structure.** Look for duplicate `cNvPr` ids within a slide, `r:id` references with no
   relationship, parts missing from `[Content_Types].xml`, and duplicate `sldId` values. LibreOffice
   draws a file with any of these without complaint, so the visual check cannot find them, and
   PowerPoint turns them into a repair prompt. Schema validation (`validate.py` in Anthropic's
   skill) does not stand in for this check; run both
2. **Look.** Render with `soffice --headless --convert-to pdf`, turn the PDF into images with
   `pdftoppm -png`, and open every image one at a time. A script that reports "no problems" has not
   looked at the page
