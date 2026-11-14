"""GTK modules shared by the widgets. Importing the package restarts the
process with gtk4-layer-shell preloaded unless LD_PRELOAD is already set,
and pins the gi versions its modules import."""

import os
import sys

import gi

# gtk4-layer-shell must be loaded before libwayland-client. A bare soname is
# resolved by the dynamic loader, so this works on any distro library layout.
if "LD_PRELOAD" not in os.environ:
    os.environ["LD_PRELOAD"] = "libgtk4-layer-shell.so.0"
    os.execvp(sys.executable, [sys.executable, *sys.argv])  # noqa: S606  (this same command)

gi.require_versions(
    {"Gdk": "4.0", "Gtk": "4.0", "Gtk4LayerShell": "1.0", "Pango": "1.0"}
)
