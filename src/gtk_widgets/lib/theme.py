"""Theme colours and @@TOKEN@@ rendering (stdlib, no GTK).

The theme file is $GTK_WIDGETS_THEME, else the themes/current.json symlink
set by install.sh, else the bundled catppuccin-mocha.json.
"""

import json
import os
import re
from pathlib import Path

from gtk_widgets.lib.parse import ParseError, parse_colors
from gtk_widgets.lib.paths import SRC

_THEMES_DIR = SRC.parent / "themes"
_CURRENT_THEME = _THEMES_DIR / "current.json"  # symlink set by install.sh
_FALLBACK_THEME = _THEMES_DIR / "catppuccin-mocha.json"


def theme_path() -> Path:
    """$GTK_WIDGETS_THEME, else the install.sh symlink, else the bundled default."""
    override = os.environ.get("GTK_WIDGETS_THEME")
    if override:
        return Path(override)
    if _CURRENT_THEME.exists():
        return _CURRENT_THEME
    return _FALLBACK_THEME


def colors() -> dict[str, str]:
    """The theme's colours: {NAME: hex without the #}. A theme file that is
    not {"colors": {NAME: hex, ...}} raises ParseError: no widget can be
    drawn without it."""
    path = theme_path()
    match parse_colors(json.loads(path.read_text(encoding="utf-8"))):
        case ParseError() as e:
            raise ParseError(f"{path}: {e}")
        case palette:
            return palette


def render_css(css: str) -> str:
    """Replace @@TOKEN@@ placeholders in a CSS string with theme colors."""
    palette = colors()

    def replace_token(m: re.Match[str]) -> str:
        name = m.group(1)
        if name.endswith("_RAW"):
            return palette.get(name[:-4], m.group(0))
        return f"#{palette[name]}" if name in palette else m.group(0)

    return re.sub(r"@@([A-Z][A-Z0-9_]*)@@", replace_token, css)
