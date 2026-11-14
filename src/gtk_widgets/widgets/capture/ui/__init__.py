"""capture's GTK side; main.py loads gtk4-layer-shell before importing it."""

import gi

gi.require_versions(
    {"Gdk": "4.0", "GdkPixbuf": "2.0", "Graphene": "1.0", "Gsk": "4.0", "Gtk": "4.0"}
)
