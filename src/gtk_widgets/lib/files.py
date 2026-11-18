"""Whole-file saves (stdlib)."""

import os
import tempfile
from pathlib import Path


def replace_text(path: Path, text: str) -> bool:
    """Write text atomically through a temp file of its own, so two writers at
    once (a popup and a status script, a thread and the main loop) each leave a
    whole file and never take each other's temp file. False when the file
    already held the text."""
    try:
        if path.read_text() == text:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            _ = f.write(text)
        _ = Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return True
