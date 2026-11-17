"""The popup's state files, read by sway startup and dotfiles (stdlib)."""

import contextlib
import os
from pathlib import Path

# Runtime state, outside any config checkout: sway includes scale.conf,
# dotfiles' wlsunset.sh reads temperature and runs `settings-epp restore`
# at sway startup
STATE_DIR = Path.home() / ".local/state/dotfiles"


def write_state(path: Path, text: str) -> None:
    """Write a state file whole: a reader sees the old text or the new, never
    an empty or partial file."""
    path.parent.mkdir(exist_ok=True, parents=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}")
    try:
        tmp.write_text(text)
        tmp.replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
