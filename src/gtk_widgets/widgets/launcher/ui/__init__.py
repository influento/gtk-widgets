"""launcher's GTK side; main.py preloads gtk4-layer-shell before importing it."""

import gi

gi.require_versions({"Gdk": "4.0", "GdkPixbuf": "2.0", "Gtk": "4.0", "Pango": "1.0"})
