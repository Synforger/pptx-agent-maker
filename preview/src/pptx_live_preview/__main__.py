"""CLI: watch a .pptx (or a folder of .pptx files) and live-reload rendered slides.

Save the deck (or regenerate it from a script) and the browser page re-renders
automatically. Rendering uses LibreOffice + pdftoppm; the page refreshes over
Server-Sent Events. Point at a folder to get every .pptx inside it from a single
URL (new decks appearing in the folder show up without a restart).
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

from .render import DEFAULT_DPI
from .server import QuietThreadingHTTPServer, make_handler
from .state import DeckSet, watch


def serve(deckset: DeckSet, port: int, no_open: bool) -> int:
    what = f"folder {deckset.source}" if deckset.is_folder else deckset.source.name
    print(f"scanning {deckset.source} ...")
    deckset.rescan_and_rerender(force=True)  # 起動時は落ち着くのを待たず即描く

    names = deckset.deck_names()
    print(f"found {len(names)} deck(s): {', '.join(names) or '(none yet)'}")
    for name in names:
        deck = deckset.deck(name)
        if deck is not None and deck.error:
            print(f"warning: {name}: {deck.error}", file=sys.stderr)

    server = QuietThreadingHTTPServer(("127.0.0.1", port), make_handler(deckset))
    _host, bound_port = server.server_address
    url = f"http://127.0.0.1:{bound_port}/"

    threading.Thread(target=watch, args=(deckset,), daemon=True).start()

    print(f"pptx-live-preview serving {what}")
    print(f"  open: {url}")
    print("  edit a deck and save — pages update automatically. Ctrl-C to stop.")
    if not no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping.")
    finally:
        server.shutdown()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pptx-live-preview",
        description="Watch a .pptx (or a folder of .pptx files) and live-reload rendered slides in the browser.",
    )
    parser.add_argument("path", type=Path, help="path to a .pptx, or a folder containing .pptx files")
    parser.add_argument("--port", type=int, default=0, help="port (0 = auto)")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI,
                        help=f"render DPI (default {DEFAULT_DPI})")
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    args = parser.parse_args(argv)

    path = args.path.expanduser().resolve()
    if not path.exists():
        print(f"error: not found: {path}", file=sys.stderr)
        return 1

    return serve(DeckSet(path, args.dpi), args.port, args.no_open)


if __name__ == "__main__":
    raise SystemExit(main())
