"""Theme colours and @@TOKEN@@ rendering (stdlib, no GTK).

The theme file is $GTK_WIDGETS_THEME, else the themes/current.json symlink
set by install.sh, else the bundled catppuccin-mocha.json.
"""

import json
import os
import re

_THEMES_DIR = os.path.join(os.path.dirname(__file__), "..", "themes")
_CURRENT_THEME = os.path.join(_THEMES_DIR, "current.json")  # symlink set by install.sh
_FALLBACK_THEME = os.path.join(_THEMES_DIR, "catppuccin-mocha.json")


def theme_path():
    """$GTK_WIDGETS_THEME, else the install.sh symlink, else the bundled default."""
    override = os.environ.get("GTK_WIDGETS_THEME")
    if override:
        return override
    if os.path.exists(_CURRENT_THEME):
        return _CURRENT_THEME
    return _FALLBACK_THEME


def colors():
    """Load theme colors from JSON. Returns dict of {NAME: hex_value}."""
    with open(theme_path()) as f:
        return json.load(f)["colors"]


def render_css(css):
    """Replace @@TOKEN@@ placeholders in a CSS string with theme colors."""
    palette = colors()
    def replace_token(m):
        name = m.group(1)
        if name.endswith("_RAW"):
            return palette.get(name[:-4], m.group(0))
        return f"#{palette[name]}" if name in palette else m.group(0)
    return re.sub(r"@@([A-Z][A-Z0-9_]*)@@", replace_token, css)
