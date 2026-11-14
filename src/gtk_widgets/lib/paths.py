"""Where this checkout's code lives, for children that run our modules (stdlib)."""

import os
import sys
from pathlib import Path

# The directory that holds the gtk_widgets package
SRC = Path(__file__).resolve().parents[2]


def module_child(module: str) -> tuple[list[str], dict[str, str]]:
    """The argv and environment that run one of our modules in a child Python."""
    path = os.pathsep.join(p for p in (str(SRC), os.environ.get("PYTHONPATH")) if p)
    return [sys.executable, "-m", module], {**os.environ, "PYTHONPATH": path}
