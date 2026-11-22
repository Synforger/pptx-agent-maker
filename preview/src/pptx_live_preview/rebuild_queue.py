"""Run forced redraws one after another, however often they are asked for.

Each `DeckSet` holds one.
"""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable


class RebuildQueue:
    """One redraw running and at most one waiting after it.

    The waiting one is kept because a deck can change after the running one has read it.
    """

    def __init__(self, work: Callable[[], None]) -> None:
        self.work = work
        self._lock = threading.Lock()
        self._is_running = False
        self._is_waiting = False

    def add(self) -> None:
        """Ask for a redraw and return at once."""
        with self._lock:
            if self._is_running:
                self._is_waiting = True
                return
            self._is_running = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        while True:
            try:
                self.work()
            except Exception:  # one failed redraw must not keep the next from starting
                traceback.print_exc()
            with self._lock:
                if not self._is_waiting:
                    self._is_running = False
                    return
                self._is_waiting = False
