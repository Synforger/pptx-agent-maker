# pptx-live-preview

> Live-reloading local preview for PowerPoint decks: save the pptx, see it re-render in the browser.

Point it at a `.pptx` (or a folder of them) and open the printed URL. Every save — whether you
edited the deck by hand or regenerated it from a script — re-renders the slides and refreshes the
page on its own. Useful when a build pipeline produces decks and you want to watch the result
without opening PowerPoint on every iteration.

## Quick start

```bash
# Prerequisites: LibreOffice (soffice) and poppler (pdftoppm) on PATH.
# `task doctor` diagnoses the toolchain floor.
task setup

.venv/bin/pptx-live-preview path/to/deck.pptx     # one deck
.venv/bin/pptx-live-preview path/to/deck-folder/  # every deck in the folder, as tabs
```

Options: `--port` (0 = pick a free one), `--dpi` (default 200), `--no-open` (do not launch a browser).

## Reviewing a deck

The page is built for reading a deck end to end, not just for watching it reload.

- **Page list** down the left: click to jump; the current page follows your scrolling
- **Grid overview** (`g`) to see the whole deck at once
- **Zoom** (`f`) fills the screen with one page, the way it will be presented
- **Compare** (`c`) puts two decks side by side, each with its own page track underneath, so decks
  grown from one skeleton can be lined up against each other page by page
- **Speaker notes** (`n`) in a side pane, read straight from the `.pptx`
- **Deck switching** from the menu at the top left, or `Ctrl`+`←` / `Ctrl`+`→`

Keys: `←` `→` (or `PgUp` / `PgDn`) move a page, `Home` / `End` jump to the ends, typing digits
followed by `Enter` goes to that page, `Space` goes back from an overlay, `?` lists the lot.

## How it works

LibreOffice converts the deck to PDF, then pdftoppm rasterises each page to JPEG twice: full size
for reading, small for the page list. Its user profile — where it keeps settings and what it works
out about the machine — is kept under the cache directory rather than rebuilt per conversion, which
saves the start-up work on every deck; one profile per concurrent conversion,
since two processes cannot share one. Rasterising is split into page ranges across processes —
pdftoppm walks pages one at a time otherwise (byte-identical output).

Pages come out at 2667 x 1500 for a 16:9 deck, which is what a Retina display needs to show one at
1280 CSS pixels without stretching; 110dpi used to leave it upscaled. The extra resolution costs
a little render time and roughly doubles the bytes of a page, though only pages actually
looked at are fetched. Pages are fetched as they come into view — the browser's own
lazy loading is no help here, because it measures distance against the outermost scroller and this
page scrolls an inner region, so it considers every page visible. Doing it by hand, the first load fetches only the
pages on screen. The browser subscribes to Server-Sent Events and refreshes
when a new render lands. The watcher polls the file's modification time twice before rendering, so
a deck that is still being written is never picked up half-finished.

Rendered pages are kept in a store under your cache directory, named by the hash of their own
content. Two things fall out of that: a restart reuses the pages instead of re-rendering them
(seconds instead of a minute for a folder of large decks), and every image URL is immutable, so the
browser cache is always right. A deck whose bytes have not changed skips rendering entirely — including the
LibreOffice step — so a build that rewrites an unchanged deck costs nothing. The refresh button is
the one path that ignores the store and re-renders regardless.

In folder mode, decks render concurrently (capped, since each conversion costs a core and a few
hundred MB). PowerPoint lock files (`~$*.pptx`) are skipped; every other `.pptx` in the folder is
treated as a deck.

## Documentation

- For users — [`docs/`](docs/) (setup / troubleshooting / reference)
- For contributors — [`docs/internals/`](docs/internals/)
- What works today and what is planned — [`ROADMAP.md`](ROADMAP.md)

## License

MIT — see [`LICENSE`](LICENSE). Third-party dependencies are listed in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md); vulnerability reporting is described in
[`SECURITY.md`](SECURITY.md).
