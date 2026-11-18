"""A grid of background files (images, or GIFs, videos and links) from the
backgrounds folder: one chosen at a time, each removed by its x (no
confirm: the user's call). The folder is the dotfiles' one, so a removal
syncs too."""

from collections.abc import Callable
from pathlib import Path

from gtk_widgets.lib.ui.copy_label import copyable
from gtk_widgets.lib.ui.widget_base import Gtk
from gtk_widgets.widgets.webcam import links
from gtk_widgets.widgets.webcam.preview import show_thumbnail

THUMB_W, THUMB_H = 96, 54
THUMB_SCALE = 2  # thumbnails are decoded at twice their size: sharp at scale 2
PER_LINE = 4
REMOVE_GLYPH = "\u00d7"  # multiplication sign


class Gallery:
    """`chosen()` is the chosen file's path; `choose(path)` sets it (None
    when the chosen one was removed); `show_error(text)` shows a failure."""

    def __init__(
        self,
        folder: Path,
        *,
        suffixes: set[str],
        kind: str,
        chosen: Callable[[], str | None],
        choose: Callable[[str | None], None],
        show_error: Callable[[str], bool | None],
    ) -> None:
        self._folder = folder
        self._suffixes = suffixes
        self._kind = kind
        self._chosen = chosen
        self._choose = choose
        self._show_error = show_error
        self._buttons: list[Gtk.ToggleButton] = []
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.refresh()

    def refresh(self) -> None:
        """Read the folder again: after a file is added or removed."""
        while (child := self.box.get_first_child()) is not None:
            self.box.remove(child)
        self._buttons = []
        files = (
            sorted(
                p for p in self._folder.iterdir() if p.suffix.lower() in self._suffixes
            )
            if self._folder.is_dir()
            else []
        )
        if not files:
            # ~ for the home folder: a path does not wrap and widens the popup
            shown = f"~/{self._folder.relative_to(Path.home())}"
            hint = copyable(
                Gtk.Label(label=f"Put {self._kind} in {shown}", xalign=0, wrap=True),
                copy_text=str(self._folder),
            )
            hint.add_css_class("note")
            self.box.append(hint)
            return
        grid = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            max_children_per_line=PER_LINE,
            homogeneous=True,
        )
        for path in files:
            grid.append(self._tile(path))
        self.box.append(grid)

    def _tile(self, path: Path) -> Gtk.Overlay:
        thumb = Gtk.Picture(content_fit=Gtk.ContentFit.COVER)
        thumb.set_size_request(THUMB_W, THUMB_H)
        show_thumbnail(thumb, path, THUMB_SCALE, self._show_error)
        button = Gtk.ToggleButton(child=thumb, tooltip_text=path.name)
        button.add_css_class("thumb")
        # Grouped: one chosen at a time, and a click on it keeps it
        if self._buttons:
            button.set_group(self._buttons[0])
        button.set_active(self._chosen() == str(path))
        button.connect("toggled", self._on_toggled, str(path))
        self._buttons.append(button)
        # Shown on hover (style.css)
        remove = Gtk.Button(
            label=REMOVE_GLYPH,
            tooltip_text="Remove",
            halign=Gtk.Align.END,
            valign=Gtk.Align.START,
        )
        remove.add_css_class("thumb-remove")
        remove.connect("clicked", self._on_remove, path)
        tile = Gtk.Overlay(child=button)
        tile.add_css_class("thumb-tile")
        tile.add_overlay(remove)
        return tile

    def _on_toggled(self, button: Gtk.ToggleButton, path: str) -> None:
        if button.get_active():
            self._choose(path)

    def _on_remove(self, _button: Gtk.Button, path: Path) -> None:
        if links.is_link(path):
            links.forget(path)
        try:
            path.unlink(missing_ok=True)
        except OSError as e:
            _ = self._show_error(f"{path.name}: {e.strerror}")
            return
        if self._chosen() == str(path):
            self._choose(None)
        self.refresh()
