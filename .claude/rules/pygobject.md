---
paths: ["**/*.py"]
---

# UI: GTK 4 with PyGObject

- The entry point loads gtk4-layer-shell before anything imports Gtk:
  `ctypes.CDLL("libgtk4-layer-shell.so.0", mode=ctypes.RTLD_GLOBAL)`.
  Loaded later, `Gtk4LayerShell.is_supported()` is false and the window
  opens as a normal one.
- `gi.require_versions({...})` once, in the package's `__init__.py`; a
  module then imports from `gi.repository` at its top.

API: the C docs at https://docs.gtk.org/gtk4/ and
https://wmww.github.io/gtk4-layer-shell/ (Python drops the `gtk_` prefix:
`gtk_window_present` is `Gtk.Window.present`); the Python types in
`.venv/lib/python3*/site-packages/gi-stubs/repository/`.
