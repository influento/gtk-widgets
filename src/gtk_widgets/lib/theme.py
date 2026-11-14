"""Theme colours and @@TOKEN@@ rendering (stdlib, no GTK).

The theme file is $GTK_WIDGETS_THEME, else the themes/current.json symlink
set by install.sh, else the bundled catppuccin-mocha.json.
"""

import json
import os
import re
from pathlib import Path
from typing import TypeIs

from gtk_widgets.lib.paths import SRC

_THEMES_DIR = SRC.parent / "themes"
_CURRENT_THEME = _THEMES_DIR / "current.json"  # symlink set by install.sh
_FALLBACK_THEME = _THEMES_DIR / "catppuccin-mocha.json"


class ThemeError(ValueError):
    """The theme file is not {"colors": {NAME: hex, ...}}."""


def theme_path() -> Path:
    """$GTK_WIDGETS_THEME, else the install.sh symlink, else the bundled default."""
    override = os.environ.get("GTK_WIDGETS_THEME")
    if override:
        return Path(override)
    if _CURRENT_THEME.exists():
        return _CURRENT_THEME
    return _FALLBACK_THEME


def colors() -> dict[str, str]:
    """The theme's colours: {NAME: hex without the #}."""
    path = theme_path()
    data: object = json.loads(path.read_text(encoding="utf-8"))
    found = data.get("colors") if _is_json_object(data) else None
    if not _is_json_object(found):
        raise ThemeError(f"{path}: no colors object")
    palette: dict[str, str] = {}
    for name, value in found.items():
        if not isinstance(value, str):
            raise ThemeError(f"{path}: colour {name} is not a string")
        palette[name] = value
    return palette


def _is_json_object(value: object) -> TypeIs[dict[str, object]]:
    """A JSON object from json.loads: its keys are always strings."""
    return isinstance(value, dict)


def render_css(css: str) -> str:
    """Replace @@TOKEN@@ placeholders in a CSS string with theme colors."""
    palette = colors()

    def replace_token(m: re.Match[str]) -> str:
        name = m.group(1)
        if name.endswith("_RAW"):
            return palette.get(name[:-4], m.group(0))
        return f"#{palette[name]}" if name in palette else m.group(0)

    return re.sub(r"@@([A-Z][A-Z0-9_]*)@@", replace_token, css)
