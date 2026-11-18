"""The webcam settings file: load and save (stdlib). The popup writes it; the
effects engine and `webcam-apply` read it."""

import contextlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.widgets.webcam.parse import Settings, parse_settings

SETTINGS_FILE = Path.home() / ".config/gtk-widgets/webcam.json"


def load(path: Path = SETTINGS_FILE) -> Settings | ParseError:
    """The saved settings; defaults when there is no file yet."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Settings()
    except OSError as e:
        return ParseError(f"{path}: {e.strerror}")
    try:
        data: object = json.loads(text)
    except ValueError as e:
        return ParseError(f"{path}: {e}")
    match parse_settings(data):
        case ParseError() as e:
            return ParseError(f"{path}: {e}")
        case settings:
            return settings


def save(settings: Settings, path: Path = SETTINGS_FILE) -> None:
    """Write the file whole: the engine sees the old text or the new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}")
    try:
        _ = tmp.write_text(
            json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8"
        )
        _ = tmp.replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
