"""launcher's GTK side: the picker popup, the resident instance, one-shot dmenu."""

import contextlib
import os
import signal
import socket
import struct
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import override

from gi.repository import Gio, GObject, Pango

from gtk_widgets.lib.theme import render_css
from gtk_widgets.lib.ui.widget_base import (
    BASE_CSS,
    Gdk,
    GLib,
    Gtk,
    VScroller,
    install_css,
    load_css,
    place_popup,
    popup_window,
)
from gtk_widgets.widgets.launcher import match, options, protocol
from gtk_widgets.widgets.launcher.options import Options
from gtk_widgets.widgets.launcher.ui import apps as appdb
from gtk_widgets.widgets.launcher.ui import preview

_CSS = Path(__file__).resolve().parent / "style.css"

APP_ID = "dev.dotfiles.launcher"
MARGIN_TOP = 40
WIDTH = 560
ROWS = 10  # visible rows
ROW_H = 34  # listview.launcher-list > row min-height in style.css
FALLBACK_ICON = "application-x-executable"
DISPLAY_CHARS = 200  # a dmenu row shows at most this much: Pango shapes all of it
WARM_BATCH = 500  # rows whose word index is built per idle call
DRUN, DMENU = "drun", "dmenu"
_NEXT = {"j", "n"}  # with Ctrl (the us-layout key, whatever the layout)
_PREV = {"k", "p"}
_PANE = {"l": True, "h": False}  # Ctrl+l opens the preview pane, Ctrl+h closes it
_DELETE = "d"  # Ctrl+d deletes the selected row (dmenu --delete)
DELETE_ICON = "\U000f0156"  # nf-md-close
SEARCH_ICON = "\uf002"  # nf-fa-search: the prompt when none is given
# Fields of a dmenu request's header (protocol.py) after "dmenu"
_SIZE, _PROMPT, _T0, _AFTER_TAB, _ACTION, _DEL = range(1, 7)

type OnPick = Callable[[int | None], None]  # line index, protocol.ACTION or None
type Rows = list[tuple[str, Options]]


class Item(GObject.Object):
    """One list entry."""

    __gtype_name__ = "LauncherItem"

    def __init__(
        self,
        text: str,
        field: match.Field,
        *,
        extra: tuple[match.Field, ...] = (),
        icon: Gio.Icon | None = None,
        detail: str = "",
        opts: Options | None = None,
    ) -> None:
        super().__init__()
        self.text, self.field, self.extra = text, field, extra
        self.icon, self.detail = icon, detail
        self.opts = opts or {}  # dmenu row options (options.py)


class AppItem(Item):
    """A desktop entry (drun)."""

    __gtype_name__ = "LauncherAppItem"

    def __init__(self, app: appdb.App) -> None:
        super().__init__(
            app.name, app.field, extra=app.extra, icon=app.icon, detail=app.detail
        )
        self.app = app


class LineItem(Item):
    """An input line (dmenu); index is its place in the input."""

    __gtype_name__ = "LauncherLineItem"

    def __init__(self, text: str, opts: Options, index: int) -> None:
        words = [text, *opts.get("detail", []), *opts.get("meta", [])]
        super().__init__(
            text[:DISPLAY_CHARS],
            match.Field(" ".join(words)),
            detail=options.first(opts, "detail"),
            opts=opts,
        )
        self.index = index


class Row(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(spacing=10)
        self.icon = Gtk.Image(pixel_size=24)
        self.append(self.icon)
        self.slot = preview.Slot()  # dmenu rows with options
        self.append(self.slot)
        # max_width_chars=1: a long name can't widen the list, it ellipsizes
        self.label = Gtk.Label(
            xalign=0,
            hexpand=True,
            max_width_chars=1,
            ellipsize=Pango.EllipsizeMode.END,
            single_line_mode=True,
        )
        self.label.add_css_class("launcher-name")
        self.append(self.label)
        self.detail = Gtk.Label(
            max_width_chars=28, ellipsize=Pango.EllipsizeMode.MIDDLE
        )
        self.detail.add_css_class("launcher-detail")
        self.append(self.detail)
        # dmenu --delete; not focusable, so typing stays in the entry
        self.delete = Gtk.Button(
            label=DELETE_ICON,
            focusable=False,
            focus_on_click=False,
            valign=Gtk.Align.CENTER,
            tooltip_text="Delete (Ctrl+d)",
        )
        self.delete.add_css_class("launcher-delete")
        self.append(self.delete)
        self.item: Item | None = None


def display_lines(lines: list[bytes], *, after_tab: bool = False) -> Rows:
    """dmenu input lines as (text, options): the text shown and searched is
    UTF-8 (invalid bytes replaced), without the options after a NUL
    (options.py), with after_tab only what follows the first tab (cliphist's
    "<id>\t<preview>"), other tabs as two spaces. The pick is printed from
    the original bytes."""
    rows: Rows = []
    for line in lines:
        text, opts = options.split(line.decode("utf-8", "replace"))
        if after_tab:
            text = text.split("\t", 1)[-1]
        rows.append((text.replace("\t", "  "), opts))
    return rows


def _us_key(keyval: int) -> str:
    """The us-layout letter of a key press (Ctrl and the ru layout's key for
    j is Ctrl+j)."""
    code = Gdk.keyval_to_unicode(keyval)
    return match.us_keys(chr(code).lower()) if code else ""


class Picker:
    """The popup: a search entry over a lazily rendered list (Gtk.ListView),
    built once and shown/hidden. drun lists desktop entries by match tier,
    then usage, then name; dmenu lists lines by match tier, then input order,
    with an optional action button (--action). dmenu rows with options get
    thumbnails, and Right opens the preview pane beside the list (Left closes it).
    Only Esc closes it: q and every other key go to the search entry."""

    def __init__(
        self,
        app: Gtk.Application,
        launch: Callable[[appdb.App], bool] | None = None,
    ) -> None:
        """launch(app) runs a picked desktop entry; drun needs it."""
        self._launch = launch
        self.mode = ""
        self.lines: list[LineItem] = []  # dmenu
        self.drun_items: list[AppItem] = []
        self.scores: dict[str, float] = {}  # drun: app id -> usage score, at show
        self._on_pick: OnPick | None = None  # dmenu
        self._on_delete: Callable[[int], None] | None = None  # dmenu --delete
        self.pane_open = False
        self._quiet = False

        self.win, overlay = popup_window(
            app, self.dismiss, lambda _ctrl, _keyval, _code, _state: False
        )
        # The compositor closes a layer surface whose output goes away: hide
        # (and cancel a pick) instead of destroying the one window
        self.win.connect("close-request", self._on_close_request)
        # Capture phase: the entry would otherwise take Up/Down/Tab/Enter
        keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.win.add_controller(keys)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("launcher")
        box.set_size_request(WIDTH, -1)
        self.prompt = Gtk.Label()
        self.entry = Gtk.Entry(hexpand=True)
        # Not focusable: typing stays in the entry after a click
        self.action = Gtk.Button(focusable=False, focus_on_click=False, visible=False)
        box.append(self._search_row())

        self.store = Gio.ListStore(item_type=Item)
        self.selection = Gtk.SingleSelection(
            model=self.store, autoselect=True, can_unselect=False
        )
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup_row)
        factory.connect("bind", self._bind_row)
        self.list = Gtk.ListView(model=self.selection, factory=factory, focusable=False)
        self.list.add_css_class("launcher-list")
        scroller = VScroller(ROWS * ROW_H, self.list)
        scroller.set_min_content_height(ROWS * ROW_H)  # steady size while filtering
        stack = Gtk.Overlay(child=scroller)
        self.empty = Gtk.Label(
            label="No matches", visible=False, valign=Gtk.Align.START, margin_top=8
        )
        self.empty.add_css_class("launcher-empty")
        stack.add_overlay(self.empty)
        self.box, self.scroller, self.liststack = box, scroller, stack
        # The list and, while open, the preview pane beside it
        self.body = Gtk.Box(spacing=10)
        self.body.append(stack)
        self.pane = preview.Pane()
        self.body.append(self.pane)
        box.append(self.body)
        self.selection.connect("notify::selected", self._on_selected)

        place_popup(self.win, overlay, box, MARGIN_TOP)

    def _search_row(self) -> Gtk.Box:
        search = Gtk.Box(spacing=8)
        self.prompt.add_css_class("launcher-prompt")
        search.append(self.prompt)
        self.entry.add_css_class("launcher-entry")
        self.entry.connect("changed", self._on_changed)
        search.append(self.entry)
        self.action.add_css_class("launcher-action")
        self.action.connect("clicked", lambda *_: self._finish(protocol.ACTION))
        search.append(self.action)
        return search

    def _on_selected(
        self, _sel: Gtk.SingleSelection, _pspec: GObject.ParamSpec
    ) -> None:
        self._show_selected()

    def _on_close_request(self, _win: Gtk.Window) -> bool:
        self.dismiss()
        return True

    # --- rows ---

    def _setup_row(self, _factory: Gtk.SignalListItemFactory, li: Gtk.ListItem) -> None:
        li.set_focusable(False)
        row = Row()
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self._activate(li.get_position()))
        row.add_controller(click)
        row.delete.connect("clicked", lambda *_: self._delete(row.item))
        li.set_child(row)

    def _bind_row(self, _factory: Gtk.SignalListItemFactory, li: Gtk.ListItem) -> None:
        item, row = li.get_item(), li.get_child()
        if not isinstance(item, Item) or not isinstance(row, Row):
            return
        row.item = item
        row.delete.set_visible(self._on_delete is not None)
        row.label.set_text(item.text)
        row.detail.set_text(item.detail)
        row.detail.set_visible(bool(item.detail))
        row.icon.set_visible(self.mode == DRUN)
        thumbs = self.mode == DMENU and bool(item.opts)
        row.slot.set_visible(thumbs)
        row.set_size_request(
            -1, preview.THUMB_ROW_H if thumbs and row.slot.fill(item.opts) else -1
        )
        if thumbs and options.first(item.opts, "kind") == "missing":
            row.label.add_css_class("launcher-missing")
        else:
            row.label.remove_css_class("launcher-missing")
        if self.mode == DRUN:
            if item.icon is not None:
                row.icon.set_from_gicon(item.icon)
            else:
                row.icon.set_from_icon_name(FALLBACK_ICON)

    # --- modes ---

    def set_apps(self, apps: list[appdb.App]) -> None:
        self.drun_items = [AppItem(a) for a in apps]
        if self.mode == DRUN and self.win.get_visible():
            self._refilter()

    def toggle(self, usage: appdb.Usage, t0: str | None = None) -> None:
        if self.win.get_visible():
            self.dismiss()
        else:
            self.show_drun(usage, t0)

    def show_drun(self, usage: appdb.Usage, t0: str | None = None) -> None:
        self._drop_pick()
        self.mode = DRUN
        self.pane_open = False
        self._layout()
        self.action.set_visible(False)
        self.lines = []
        now = time.time()
        self.scores = {it.app.id: usage.score(it.app.id, now) for it in self.drun_items}
        self.prompt.set_text(SEARCH_ICON)
        self.entry.set_placeholder_text("Search apps")
        self._present(t0)

    def show_dmenu(
        self,
        rows: Rows,
        prompt: str,
        on_pick: OnPick,
        *,
        t0: str | None = None,
        action: str = "",
        on_delete: Callable[[int], None] | None = None,
    ) -> None:
        """on_pick(index, protocol.ACTION or None) is called once: pick, the
        action button, Esc, or superseded. With on_delete, rows get a cross
        (and Ctrl+d) that removes the row and calls on_delete(index)."""
        self._drop_pick()
        self.mode = DMENU
        self._on_pick = on_pick
        self._on_delete = on_delete
        self.action.set_label(action)
        self.action.set_visible(bool(action))
        self.lines = [LineItem(t, o, i) for i, (t, o) in enumerate(rows)]
        self.pane_open = False  # every show starts compact
        self._layout()
        self.prompt.set_text(prompt or SEARCH_ICON)
        self.entry.set_placeholder_text("Filter")
        self._present(t0)
        GLib.idle_add(self._warm, self.lines, 0)

    def _warm(self, lines: list[LineItem], start: int) -> bool:
        """Build a long list's word index between frames, so the first
        keystroke doesn't pay for it."""
        if lines is not self.lines:
            return GLib.SOURCE_REMOVE
        end = min(len(lines), start + WARM_BATCH)
        for it in lines[start:end]:
            _ = it.field.words  # cached on first access
        if end < len(lines):
            GLib.idle_add(self._warm, lines, end)
        return GLib.SOURCE_REMOVE

    def abort(self, on_pick: OnPick) -> None:
        """The dmenu caller went away: close its pick if it is still showing."""
        if self._on_pick is not None and self._on_pick == on_pick:
            self._finish(None)

    def dismiss(self) -> None:
        if self._on_pick is not None:
            self._finish(None)
        else:
            self.hide()

    def hide(self) -> None:
        self.pane.stop()
        self.win.set_visible(False)
        if self.mode == DMENU:  # free a long list; the next show rebuilds it
            self.lines = []
            self.store.remove_all()

    def _drop_pick(self) -> None:
        """A new show replaces a pending dmenu pick: its caller gets None."""
        on_pick, self._on_pick = self._on_pick, None
        self._on_delete = None
        if on_pick is not None:
            on_pick(None)

    def _finish(self, index: int | None) -> None:
        on_pick, self._on_pick = self._on_pick, None
        self._on_delete = None
        self.hide()
        if on_pick is not None:
            on_pick(index)

    def _present(self, t0: str | None) -> None:
        self._quiet = True
        self.entry.set_text("")
        self._quiet = False
        self._refilter()
        self.win.set_focus(self.entry)
        self.win.present()
        self.entry.grab_focus_without_selecting()
        if t0:
            self._trace(t0)

    def _trace(self, t0: str) -> None:
        """Print the time from t0 (ns since the epoch) to the first frame."""
        try:
            start = int(t0)
        except ValueError:
            return
        clock = self.win.get_frame_clock()
        if clock is None:
            return

        def painted(c: Gdk.FrameClock) -> None:
            c.disconnect(handler)
            print(
                f"launcher: {self.mode} first frame "
                f"{(time.time_ns() - start) / 1e6:.1f} ms after the request",
                file=sys.stderr,
                flush=True,
            )

        handler = clock.connect("after-paint", painted)

    # --- search ---

    def _on_changed(self, _entry: Gtk.Entry) -> None:
        if not self._quiet:
            self._refilter()

    def _drun_result(self, variants: tuple[str, ...]) -> list[AppItem]:
        scores = self.scores

        def usage_key(it: AppItem) -> tuple[float, tuple[str, str]]:
            return -scores.get(it.app.id, 0.0), it.app.sort

        if not variants:
            return sorted(self.drun_items, key=usage_key)
        ranked: list[tuple[int, tuple[float, tuple[str, str]], AppItem]] = []
        for it in self.drun_items:
            key = match.rank(variants, it.field, it.extra)
            if key is not None:
                ranked.append((key, usage_key(it), it))
        ranked.sort(key=lambda t: (t[0], t[1]))
        return [it for _, _, it in ranked]

    def _dmenu_result(self, variants: tuple[str, ...]) -> list[LineItem]:
        if not variants:
            return self.lines
        ranked: list[tuple[int, int, LineItem]] = []
        for i, it in enumerate(self.lines):
            key = match.rank(variants, it.field)
            if key is not None:
                ranked.append((key, i, it))
        ranked.sort(key=lambda t: (t[0], t[1]))
        return [it for _, _, it in ranked]

    def _refilter(self) -> None:
        variants = match.query_variants(self.entry.get_text())
        result: Sequence[Item] = (
            self._drun_result(variants)
            if self.mode == DRUN
            else self._dmenu_result(variants)
        )
        self.store.splice(0, self.store.get_n_items(), result)
        self.empty.set_visible(not result)
        if result:
            self.selection.set_selected(0)
            self.list.scroll_to(0, Gtk.ListScrollFlags.NONE, None)
        self._show_selected()  # the row at 0 may be a new one

    # --- keys ---

    def _on_key(
        self,
        _ctrl: Gtk.EventControllerKey,
        keyval: int,
        _code: int,
        state: Gdk.ModifierType,
    ) -> bool:
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if self._pane_key(keyval, state, ctrl=ctrl):
            return True
        if keyval == Gdk.KEY_Escape:
            self.dismiss()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_ISO_Enter):
            self._activate(self.selection.get_selected())
            return True
        if ctrl and _us_key(keyval) == _DELETE and self._on_delete is not None:
            pos = self.selection.get_selected()
            if pos != Gtk.INVALID_LIST_POSITION:
                self._delete(self.store.get_item(pos))
            return True
        step = self._step(keyval, state, ctrl=ctrl)
        if step is None:
            return False
        self._move(step)
        return True

    @staticmethod
    def _step(keyval: int, state: Gdk.ModifierType, *, ctrl: bool) -> int | None:
        """How many rows a key moves the selection, or None."""
        if keyval == Gdk.KEY_ISO_Left_Tab or (
            keyval == Gdk.KEY_Tab and state & Gdk.ModifierType.SHIFT_MASK
        ):
            return -1
        if keyval in (Gdk.KEY_Down, Gdk.KEY_KP_Down, Gdk.KEY_Tab):
            return 1
        if keyval in (Gdk.KEY_Up, Gdk.KEY_KP_Up):
            return -1
        if keyval in (Gdk.KEY_Page_Down, Gdk.KEY_KP_Page_Down):
            return ROWS - 1
        if keyval in (Gdk.KEY_Page_Up, Gdk.KEY_KP_Page_Up):
            return -(ROWS - 1)
        if ctrl and _us_key(keyval) in _NEXT:
            return 1
        if ctrl and _us_key(keyval) in _PREV:
            return -1
        return None

    def _pane_key(self, keyval: int, state: Gdk.ModifierType, *, ctrl: bool) -> bool:
        """Right at the end of the filter text opens the pane, Left at its
        start closes it; elsewhere they move the caret. Ctrl+l/Ctrl+h open and
        close it wherever the caret is. Ctrl+Left/Right page through a row's
        files while it is open."""
        if not self._has_previews():
            return False
        vim = _us_key(keyval) if ctrl else ""
        if vim in _PANE and not state & (
            Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.ALT_MASK
        ):
            if _PANE[vim] != self.pane_open:
                self._set_pane(open_=_PANE[vim])
            return True
        left = keyval in (Gdk.KEY_Left, Gdk.KEY_KP_Left)
        right = keyval in (Gdk.KEY_Right, Gdk.KEY_KP_Right)
        if not (left or right) or state & (
            Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.ALT_MASK
        ):
            return False
        if ctrl:
            if self.pane_open:
                self.pane.page(1 if right else -1)
            return self.pane_open
        caret = self.entry.get_position()
        if right and not self.pane_open and caret == len(self.entry.get_text()):
            self._set_pane(open_=True)
            return True
        if left and self.pane_open and caret == 0:
            self._set_pane(open_=False)
            return True
        return False

    # --- preview pane ---

    def _has_previews(self) -> bool:
        return self.mode == DMENU and any(it.opts for it in self.lines)

    def _set_pane(self, *, open_: bool) -> None:
        self.pane_open = open_
        self._layout()
        self._show_selected()

    def _layout(self) -> None:
        """Compact (the list alone, as wide and tall as ever), or the pane open:
        the popup takes the output but MARGIN_TOP and 40 px around, and the
        list keeps its width beside the pane."""
        open_ = self.pane_open and self._has_previews()
        self.pane.set_visible(open_)
        list_w = WIDTH - 20  # .launcher padding
        self.liststack.set_size_request(list_w, -1)
        if not open_:
            self.pane.stop()
            self.box.set_size_request(WIDTH, -1)
            self._list_height(ROWS * ROW_H)
            return
        mon = self._monitor()
        width = mon.width - 80
        tall = mon.height - MARGIN_TOP - 40 - 92  # padding, search row, spacing
        self.box.set_size_request(width, -1)
        self._list_height(tall)
        self.pane.set_view_size(width - 20 - list_w - 10 - 24, tall - 24 - 64)

    def _monitor(self) -> Gdk.Rectangle:
        """The geometry of the popup's output, or of the first one."""
        display = self.win.get_display()
        surface = self.win.get_surface()
        mon = display.get_monitor_at_surface(surface) if surface is not None else None
        return (mon or display.get_monitors()[0]).get_geometry()

    def _list_height(self, h: int) -> None:
        # GTK refuses a max below the current min: clear the min first
        self.scroller.set_min_content_height(-1)
        self.scroller.set_max_content_height(h)
        self.scroller.set_min_content_height(h)

    def _show_selected(self) -> None:
        if not (self.pane_open and self._has_previews()):
            return
        pos = self.selection.get_selected()
        self.pane.show_item(
            self.store.get_item(pos) if pos != Gtk.INVALID_LIST_POSITION else None
        )

    def _move(self, delta: int) -> None:
        n = self.store.get_n_items()
        if not n:
            return
        pos = self.selection.get_selected()
        pos = 0 if pos == Gtk.INVALID_LIST_POSITION else pos
        pos = max(0, min(n - 1, pos + delta))
        self.selection.set_selected(pos)
        self.list.scroll_to(pos, Gtk.ListScrollFlags.NONE, None)

    def _delete(self, item: Item | None) -> None:
        """Drop a dmenu row (--delete) for good, keeping the selection where
        it was, and tell the caller."""
        if self._on_delete is None or not isinstance(item, LineItem):
            return
        found, pos = self.store.find(item)
        if not found:
            return
        sel = self.selection.get_selected()
        self.lines.remove(item)  # in place: _warm() checks the list's identity
        self.store.remove(pos)
        n = self.store.get_n_items()
        self.empty.set_visible(not n)
        if n:
            if sel in {Gtk.INVALID_LIST_POSITION, pos}:
                sel = min(pos, n - 1)
            elif sel > pos:
                sel -= 1
            self.selection.set_selected(sel)
        self._show_selected()
        self._on_delete(item.index)

    def _activate(self, pos: int) -> None:
        item = self.store.get_item(pos) if pos != Gtk.INVALID_LIST_POSITION else None
        match item:
            case AppItem() if self._launch is not None:
                self.hide()
                GLib.idle_add(self._launch, item.app)  # after the unmap is out
            case LineItem():
                self._finish(item.index)
            case _:
                pass


# --- the resident instance ---


class Request:
    """One CLI connection: a header line, for dmenu the stdin bytes, then the
    socket stays open until the pick; EOF on it means the CLI went away."""

    MAX_HEADER = 1 << 16
    RECV_BYTES = 1 << 16

    def __init__(
        self, picker: Picker, toggle: Callable[[str | None], None], conn: socket.socket
    ) -> None:
        self.picker, self.toggle, self.conn = picker, toggle, conn
        self.buf = bytearray()
        self.fields: list[str] | None = None
        self.waiting = False
        self.watch = GLib.unix_fd_add_full(
            GLib.PRIORITY_HIGH,
            conn.fileno(),
            GLib.IOCondition.IN | GLib.IOCondition.HUP | GLib.IOCondition.ERR,
            lambda _fd, _cond: self._readable(),
        )

    def _readable(self) -> bool:
        try:
            chunk = self.conn.recv(self.RECV_BYTES)
        except BlockingIOError:
            return GLib.SOURCE_CONTINUE
        except OSError:
            chunk = b""
        if not chunk:
            waiting = self.waiting
            self.close()
            if waiting:
                self.picker.abort(self.reply)
            return GLib.SOURCE_REMOVE
        if not self.waiting:
            self.buf += chunk
            self._parse()
        return GLib.SOURCE_CONTINUE if self.watch else GLib.SOURCE_REMOVE

    def _parse(self) -> None:
        if self.fields is None:
            nl = self.buf.find(b"\n")
            if nl < 0:
                if len(self.buf) > self.MAX_HEADER:
                    self.close()
                return
            self.fields = protocol.parse_header(bytes(self.buf[:nl]))
            del self.buf[: nl + 1]
            if self.fields[0] == "toggle":
                self.close()
                self.toggle(self.fields[1] if len(self.fields) > 1 else None)
                return
            if (
                self.fields[0] != "dmenu"
                or len(self.fields) <= _T0
                or not self.fields[_SIZE].isdigit()
            ):
                self.close()
                return
        fields = self.fields
        need = int(fields[_SIZE])
        if len(self.buf) < need:
            return
        lines = protocol.split_lines(bytes(self.buf[:need]))
        self.buf = bytearray()
        self.waiting = True
        after_tab = len(fields) > _AFTER_TAB and fields[_AFTER_TAB] == "1"
        delete = len(fields) > _DEL and fields[_DEL] == "1"
        self.picker.show_dmenu(
            display_lines(lines, after_tab=after_tab),
            fields[_PROMPT],
            self.reply,
            t0=fields[_T0],
            action=fields[_ACTION] if len(fields) > _ACTION else "",
            on_delete=self.deleted if delete else None,
        )

    def deleted(self, index: int) -> None:
        """A row was deleted: the CLI runs its --delete command for it."""
        if not self.waiting:
            return
        with contextlib.suppress(OSError):
            self.conn.settimeout(None)  # blocking
            self.conn.sendall(b"del %d\n" % index)
            self.conn.settimeout(0.0)  # non-blocking

    def reply(self, index: int | None) -> None:
        if not self.waiting:
            return
        self.waiting = False
        with contextlib.suppress(OSError):
            self.conn.settimeout(None)  # blocking
            self.conn.sendall(b"%d\n" % (-1 if index is None else index))
        self.close()

    def close(self) -> None:
        self.waiting = False
        if self.watch:
            watch, self.watch = self.watch, 0
            GLib.source_remove(watch)
        self.conn.close()


class Server:
    """Listens on protocol.socket_path() for the CLI. The GApplication name
    already makes this the only instance on the session bus, so a leftover
    socket file (a killed instance) is simply replaced."""

    BACKLOG = 16

    def __init__(self, picker: Picker, toggle: Callable[[str | None], None]) -> None:
        self.picker, self.toggle = picker, toggle
        self.path = Path(protocol.socket_path())
        self.sock = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM | socket.SOCK_NONBLOCK | socket.SOCK_CLOEXEC,
        )
        self.path.unlink(missing_ok=True)
        self.sock.bind(str(self.path))
        self.path.chmod(0o600)
        self.sock.listen(self.BACKLOG)
        self.inode = self.path.stat().st_ino
        self.watch = GLib.unix_fd_add_full(
            GLib.PRIORITY_HIGH,
            self.sock.fileno(),
            GLib.IOCondition.IN,
            lambda _fd, _cond: self._accept(),
        )

    def _accept(self) -> bool:
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:  # BlockingIOError: all taken
                break
            creds = conn.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
            )
            if struct.unpack("3i", creds)[1] != os.getuid():
                conn.close()
                continue
            conn.settimeout(0.0)  # non-blocking
            Request(self.picker, self.toggle, conn)
        return GLib.SOURCE_CONTINUE

    def close(self) -> None:
        GLib.source_remove(self.watch)
        self.sock.close()
        with contextlib.suppress(OSError):
            if self.path.stat().st_ino == self.inode:
                self.path.unlink()


class Launcher(Gtk.Application):
    RELOAD_DELAY_MS = 250  # a package install changes many entries at once

    def __init__(self, *, hidden: bool) -> None:
        super().__init__(application_id=APP_ID)
        self._hidden = hidden  # --daemon: the first activation doesn't show
        self._t0 = os.environ.pop("LAUNCHER_T0", None)  # cold start: trace it
        self._reload_id = 0
        self.picker: Picker | None = None
        self.server: Server | None = None
        self.usage = appdb.Usage()
        self._monitor: Gio.AppInfoMonitor | None = None

    @override
    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self.hold()  # hidden between shows
        appdb.child_environment()
        install_css(render_css(BASE_CSS) + load_css(_CSS))
        self.picker = picker = Picker(self, self.launch)
        self._reload()
        # Emits once per change, and again only after the next get_all()
        self._monitor = Gio.AppInfoMonitor.get()
        self._monitor.connect("changed", self._apps_changed)
        self.server = Server(picker, self.toggle)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._on_signal)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self._on_signal)

    def _on_signal(self) -> bool:
        self.quit()
        return GLib.SOURCE_REMOVE

    @override
    def do_activate(self) -> None:
        # A launch that lost the race to start the instance lands here too
        t0, self._t0 = self._t0, None
        if self._hidden:
            self._hidden = False
            return
        self.toggle(t0)

    @override
    def do_shutdown(self) -> None:
        if self.server:
            self.server.close()
        Gtk.Application.do_shutdown(self)

    def toggle(self, t0: str | None = None) -> None:
        if self.picker is not None:
            self.picker.toggle(self.usage, t0)

    def _apps_changed(self, _monitor: Gio.AppInfoMonitor) -> None:
        if self._reload_id:
            GLib.source_remove(self._reload_id)
        self._reload_id = GLib.timeout_add(self.RELOAD_DELAY_MS, self._reload)

    def _reload(self) -> bool:
        self._reload_id = 0
        if self.picker is not None:
            self.picker.set_apps(appdb.load_apps())
        return GLib.SOURCE_REMOVE

    def launch(self, app: appdb.App) -> bool:
        display = Gdk.Display.get_default()
        if display is None:
            return GLib.SOURCE_REMOVE
        error = appdb.launch(app.info, display.get_app_launch_context())
        if error:
            appdb.notify_error(f"Couldn't launch {app.name}", error)
        else:
            self.usage.bump(app.id)
        return GLib.SOURCE_REMOVE


class DmenuOnce(Gtk.Application):
    """dmenu with no instance running: this process shows the picker, prints
    the pick and exits."""

    def __init__(
        self,
        lines: list[bytes],
        prompt: str,
        *,
        after_tab: bool,
        action: str,
        delete: str,
    ) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.lines, self.prompt, self.after_tab = lines, prompt, after_tab
        self.action, self.delete = action, delete
        self.status = 1
        self.picker: Picker | None = None

    @override
    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        install_css(render_css(BASE_CSS) + load_css(_CSS))
        self.picker = Picker(self)

    @override
    def do_activate(self) -> None:
        if self.picker is None:
            return
        self.picker.show_dmenu(
            display_lines(self.lines, after_tab=self.after_tab),
            self.prompt,
            self._picked,
            t0=os.environ.get("LAUNCHER_T0"),
            action=self.action,
            on_delete=self._deleted if self.delete else None,
        )

    def _deleted(self, index: int) -> None:
        protocol.run_delete(self.delete, self.lines[index])

    def _picked(self, index: int | None) -> None:
        if index == protocol.ACTION:
            self.status = protocol.ACTION_STATUS
        elif index is not None:
            sys.stdout.buffer.write(self.lines[index] + b"\n")
            sys.stdout.flush()
            self.status = 0
        self.quit()


def run_resident(*, hidden: bool) -> int:
    app = Launcher(hidden=hidden)
    if hidden:
        app.register(None)
        if app.get_is_remote():
            return 0  # already running (its socket was not where we looked)
    return app.run([sys.argv[0]])


def run_dmenu_once(prompt: str, *, after_tab: bool, action: str, delete: str) -> int:
    lines = protocol.split_lines(sys.stdin.buffer.read())
    app = DmenuOnce(lines, prompt, after_tab=after_tab, action=action, delete=delete)
    app.run([sys.argv[0]])
    return app.status
