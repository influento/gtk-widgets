"""Run a widget's work on a daemon thread without losing its bugs."""

import threading
from collections.abc import Callable

from gi.repository import GLib


def in_background(
    task: Callable[[], None], on_bug: Callable[[str], bool | None]
) -> None:
    """Run `task` on a daemon thread. Nobody waits on that thread, so a bug in
    it would leave the popup showing its progress text: an exception calls
    `on_bug("bug: <exception>")` on the main thread, then raises again for its
    traceback."""

    def run() -> None:
        try:
            task()
        except Exception as e:
            GLib.idle_add(on_bug, f"bug: {e}")
            raise

    threading.Thread(target=run, daemon=True).start()
