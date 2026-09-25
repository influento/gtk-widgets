"""launcher's GTK side: the picker popup, the resident instance, one-shot dmenu."""

import os
import signal
import socket
import struct
import sys
import time

_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib.widget_base import (BASE_CSS, Gdk, GLib, Gtk, VScroller, install_css,  # noqa: E402
                             load_css, place_popup, popup_window, render_css)

from gi.repository import Gio, GObject, Pango  # noqa: E402

import apps as appdb  # noqa: E402
import match  # noqa: E402
import protocol  # noqa: E402

APP_ID = "dev.dotfiles.launcher"
MARGIN_TOP = 40
WIDTH = 560
ROWS = 10    # visible rows
ROW_H = 34   # listview.launcher-list > row min-height in style.css
FALLBACK_ICON = "application-x-executable"
DISPLAY_CHARS = 200  # a dmenu row shows at most this much: Pango shapes all of it
DRUN, DMENU = "drun", "dmenu"
_NEXT = {"j", "n"}  # with Ctrl (the us-layout key, whatever the layout)
_PREV = {"k", "p"}


class Item(GObject.Object):
    """One list entry. ref is the apps.App (drun) or the line index (dmenu)."""

    __gtype_name__ = "LauncherItem"

    def __init__(self, text, field, extra=(), icon=None, detail="", ref=None):
        super().__init__()
        self.text, self.field, self.extra = text, field, extra
        self.icon, self.detail, self.ref = icon, detail, ref


class Row(Gtk.Box):
    def __init__(self):
        super().__init__(spacing=10)
        self.icon = Gtk.Image(pixel_size=24)
        self.append(self.icon)
        # max_width_chars=1: a long name can't widen the list, it ellipsizes
        self.label = Gtk.Label(xalign=0, hexpand=True, max_width_chars=1,
                               ellipsize=Pango.EllipsizeMode.END, single_line_mode=True)
        self.label.add_css_class("launcher-name")
        self.append(self.label)
        self.detail = Gtk.Label(max_width_chars=28, ellipsize=Pango.EllipsizeMode.MIDDLE)
        self.detail.add_css_class("launcher-detail")
        self.append(self.detail)


def display_lines(lines, after_tab=False):
    """dmenu input lines as shown and searched: UTF-8 (invalid bytes replaced),
    with after_tab only what follows the first tab (cliphist's "<id>\t<preview>"),
    other tabs as two spaces. The pick is printed from the original bytes."""
    texts = (line.decode("utf-8", "replace") for line in lines)
    if after_tab:
        texts = (t.split("\t", 1)[-1] for t in texts)
    return [t.replace("\t", "  ") for t in texts]


def _us_key(keyval):
    """The us-layout letter of a key press (Ctrl+о on ru is Ctrl+j)."""
    code = Gdk.keyval_to_unicode(keyval)
    return match.us_keys(chr(code).lower()) if code else ""


class Picker:
    """The popup: a search entry over a lazily rendered list (Gtk.ListView),
    built once and shown/hidden. drun lists desktop entries by match tier,
    then usage, then name; dmenu lists lines by match tier, then input order.
    Only Esc closes it: q and every other key go to the search entry."""

    def __init__(self, app):
        self.app = app
        self.mode = None
        self.items = []
        self.drun_items = []
        self.scores = {}      # drun: app id -> usage score, taken at show
        self._on_pick = None  # dmenu: callback(line index or None)
        self._quiet = False

        self.win, overlay = popup_window(app, self.dismiss, lambda *_: False)
        # The compositor closes a layer surface whose output goes away: hide
        # (and cancel a pick) instead of destroying the one window
        self.win.connect("close-request", lambda *_: self.dismiss() or True)
        # Capture phase: the entry would otherwise take Up/Down/Tab/Enter
        keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.win.add_controller(keys)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("launcher")
        box.set_size_request(WIDTH, -1)

        search = Gtk.Box(spacing=8)
        self.prompt = Gtk.Label()
        self.prompt.add_css_class("launcher-prompt")
        search.append(self.prompt)
        self.entry = Gtk.Entry(hexpand=True)
        self.entry.add_css_class("launcher-entry")
        self.entry.connect("changed", self._on_changed)
        search.append(self.entry)
        box.append(search)

        self.store = Gio.ListStore(item_type=Item)
        self.selection = Gtk.SingleSelection(model=self.store, autoselect=True,
                                             can_unselect=False)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup_row)
        factory.connect("bind", self._bind_row)
        self.list = Gtk.ListView(model=self.selection, factory=factory, focusable=False)
        self.list.add_css_class("launcher-list")
        scroller = VScroller(ROWS * ROW_H, self.list)
        scroller.set_min_content_height(ROWS * ROW_H)  # steady size while filtering
        stack = Gtk.Overlay(child=scroller)
        self.empty = Gtk.Label(label="No matches", visible=False,
                               valign=Gtk.Align.START, margin_top=8)
        self.empty.add_css_class("launcher-empty")
        stack.add_overlay(self.empty)
        box.append(stack)

        place_popup(self.win, overlay, box, MARGIN_TOP)

    # --- rows ---

    def _setup_row(self, _factory, li):
        li.set_focusable(False)
        row = Row()
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self._activate(li.get_position()))
        row.add_controller(click)
        li.set_child(row)

    def _bind_row(self, _factory, li):
        item, row = li.get_item(), li.get_child()
        row.label.set_text(item.text)
        row.detail.set_text(item.detail)
        row.detail.set_visible(bool(item.detail))
        row.icon.set_visible(self.mode == DRUN)
        if self.mode == DRUN:
            if item.icon is not None:
                row.icon.set_from_gicon(item.icon)
            else:
                row.icon.set_from_icon_name(FALLBACK_ICON)

    # --- modes ---

    def set_apps(self, apps):
        self.drun_items = [Item(a.name, a.field, a.extra, a.icon, a.detail, a) for a in apps]
        if self.mode == DRUN:
            self.items = self.drun_items
            if self.win.get_visible():
                self._refilter()

    def toggle(self, usage, t0=None):
        if self.win.get_visible():
            self.dismiss()
        else:
            self.show_drun(usage, t0)

    def show_drun(self, usage, t0=None):
        self._drop_pick()
        self.mode = DRUN
        self.items = self.drun_items
        now = time.time()
        self.scores = {it.ref.id: usage.score(it.ref.id, now) for it in self.items}
        self.prompt.set_text("")  # nf-fa-search
        self.entry.set_placeholder_text("Search apps")
        self._present(t0)

    def show_dmenu(self, texts, prompt, on_pick, t0=None):
        """on_pick(index or None) is called once: pick, Esc, or superseded."""
        self._drop_pick()
        self.mode = DMENU
        self._on_pick = on_pick
        self.items = [Item(t[:DISPLAY_CHARS], match.Field(t), ref=i) for i, t in enumerate(texts)]
        self.prompt.set_text(prompt or "")
        self.entry.set_placeholder_text("Filter")
        self._present(t0)
        GLib.idle_add(self._warm, self.items, 0)

    def _warm(self, items, start):
        """Build a long list's word index between frames, so the first
        keystroke doesn't pay for it."""
        if items is not self.items:
            return GLib.SOURCE_REMOVE
        end = min(len(items), start + 500)
        for it in items[start:end]:
            it.field.words  # noqa: B018 (cached on first access)
        if end < len(items):
            GLib.idle_add(self._warm, items, end)
        return GLib.SOURCE_REMOVE

    def abort(self, on_pick):
        """The dmenu caller went away: close its pick if it is still showing."""
        if self._on_pick is not None and self._on_pick == on_pick:
            self._finish(None)

    def dismiss(self):
        if self._on_pick is not None:
            self._finish(None)
        else:
            self.hide()

    def hide(self):
        self.win.set_visible(False)
        if self.mode == DMENU:  # free a long list; the next show rebuilds it
            self.items = []
            self.store.remove_all()

    def _drop_pick(self):
        """A new show replaces a pending dmenu pick: its caller gets None."""
        on_pick, self._on_pick = self._on_pick, None
        if on_pick is not None:
            on_pick(None)

    def _finish(self, index):
        on_pick, self._on_pick = self._on_pick, None
        self.hide()
        if on_pick is not None:
            on_pick(index)

    def _present(self, t0):
        self._quiet = True
        self.entry.set_text("")
        self._quiet = False
        self._refilter()
        self.win.set_focus(self.entry)
        self.win.present()
        self.entry.grab_focus_without_selecting()
        if t0:
            self._trace(t0)

    def _trace(self, t0):
        """Print the time from t0 (ns since the epoch) to the first frame."""
        try:
            t0 = int(t0)
        except ValueError:
            return
        clock = self.win.get_frame_clock()
        if clock is None:
            return
        handler = None

        def painted(c):
            c.disconnect(handler)
            print(f"launcher: {self.mode} first frame {(time.time_ns() - t0) / 1e6:.1f} ms"
                  " after the request", file=sys.stderr, flush=True)
        handler = clock.connect("after-paint", painted)

    # --- search ---

    def _on_changed(self, _entry):
        if not self._quiet:
            self._refilter()

    def _refilter(self):
        variants = match.query_variants(self.entry.get_text())
        if self.mode == DRUN:
            scores = self.scores
            if variants:
                ranked = []
                for it in self.items:
                    key = match.rank(variants, it.field, it.extra)
                    if key is not None:
                        ranked.append(((key, -scores.get(it.ref.id, 0.0), it.ref.sort), it))
            else:
                ranked = [((-scores.get(it.ref.id, 0.0), it.ref.sort), it) for it in self.items]
            ranked.sort(key=lambda pair: pair[0])
            result = [it for _, it in ranked]
        elif variants:
            ranked = []
            for i, it in enumerate(self.items):
                key = match.rank(variants, it.field)
                if key is not None:
                    ranked.append((key, i, it))
            ranked.sort(key=lambda t: (t[0], t[1]))
            result = [it for _, _, it in ranked]
        else:
            result = self.items
        self.store.splice(0, self.store.get_n_items(), result)
        self.empty.set_visible(not result)
        if result:
            self.selection.set_selected(0)
            self.list.scroll_to(0, Gtk.ListScrollFlags.NONE, None)

    # --- keys ---

    def _on_key(self, _ctrl, keyval, _code, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if keyval == Gdk.KEY_Escape:
            self.dismiss()
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_ISO_Enter):
            self._activate(self.selection.get_selected())
        elif keyval == Gdk.KEY_ISO_Left_Tab or (keyval == Gdk.KEY_Tab
                                                and state & Gdk.ModifierType.SHIFT_MASK):
            self._move(-1)
        elif keyval in (Gdk.KEY_Down, Gdk.KEY_KP_Down, Gdk.KEY_Tab):
            self._move(1)
        elif keyval in (Gdk.KEY_Up, Gdk.KEY_KP_Up):
            self._move(-1)
        elif keyval in (Gdk.KEY_Page_Down, Gdk.KEY_KP_Page_Down):
            self._move(ROWS - 1)
        elif keyval in (Gdk.KEY_Page_Up, Gdk.KEY_KP_Page_Up):
            self._move(-(ROWS - 1))
        elif ctrl and _us_key(keyval) in _NEXT:
            self._move(1)
        elif ctrl and _us_key(keyval) in _PREV:
            self._move(-1)
        else:
            return False
        return True

    def _move(self, delta):
        n = self.store.get_n_items()
        if not n:
            return
        pos = self.selection.get_selected()
        pos = 0 if pos == Gtk.INVALID_LIST_POSITION else pos
        pos = max(0, min(n - 1, pos + delta))
        self.selection.set_selected(pos)
        self.list.scroll_to(pos, Gtk.ListScrollFlags.NONE, None)

    def _activate(self, pos):
        item = self.store.get_item(pos) if pos != Gtk.INVALID_LIST_POSITION else None
        if item is None:
            return
        if self.mode == DRUN:
            self.hide()
            GLib.idle_add(self.app.launch, item.ref)  # after the unmap is out
        else:
            self._finish(item.ref)


# --- the resident instance ---

class Request:
    """One CLI connection: a header line, for dmenu the stdin bytes, then the
    socket stays open until the pick; EOF on it means the CLI went away."""

    MAX_HEADER = 1 << 16

    def __init__(self, app, conn):
        self.app, self.conn = app, conn
        self.buf = bytearray()
        self.fields = None
        self.waiting = False
        self.watch = GLib.unix_fd_add_full(
            GLib.PRIORITY_HIGH, conn.fileno(),
            GLib.IOCondition.IN | GLib.IOCondition.HUP | GLib.IOCondition.ERR, self._readable)

    def _readable(self, _fd, _cond):
        try:
            chunk = self.conn.recv(1 << 16)
        except BlockingIOError:
            return GLib.SOURCE_CONTINUE
        except OSError:
            chunk = b""
        if not chunk:
            waiting = self.waiting
            self.close()
            if waiting:
                self.app.picker.abort(self.reply)
            return GLib.SOURCE_REMOVE
        if not self.waiting:
            self.buf += chunk
            self._parse()
        return GLib.SOURCE_CONTINUE if self.watch else GLib.SOURCE_REMOVE

    def _parse(self):
        if self.fields is None:
            nl = self.buf.find(b"\n")
            if nl < 0:
                if len(self.buf) > self.MAX_HEADER:
                    self.close()
                return
            self.fields = protocol.parse_header(bytes(self.buf[:nl]))
            del self.buf[:nl + 1]
            if self.fields[0] == "toggle":
                self.close()
                self.app.toggle(self.fields[1] if len(self.fields) > 1 else None)
                return
            if self.fields[0] != "dmenu" or len(self.fields) < 4 or not self.fields[1].isdigit():
                self.close()
                return
        need = int(self.fields[1])
        if len(self.buf) < need:
            return
        lines = protocol.split_lines(bytes(self.buf[:need]))
        self.buf = bytearray()
        self.waiting = True
        after_tab = len(self.fields) > 4 and self.fields[4] == "1"
        self.app.picker.show_dmenu(display_lines(lines, after_tab), self.fields[2], self.reply,
                                   self.fields[3])

    def reply(self, index):
        if not self.waiting:
            return
        self.waiting = False
        try:
            self.conn.setblocking(True)
            self.conn.sendall(b"%d\n" % (-1 if index is None else index))
        except OSError:
            pass
        self.close()

    def close(self):
        self.waiting = False
        if self.watch:
            watch, self.watch = self.watch, 0
            GLib.source_remove(watch)
        self.conn.close()


class Server:
    """Listens on protocol.socket_path() for the CLI. The GApplication name
    already makes this the only instance on the session bus, so a leftover
    socket file (a killed instance) is simply replaced."""

    def __init__(self, app):
        self.app = app
        self.path = protocol.socket_path()
        self.sock = socket.socket(socket.AF_UNIX,
                                  socket.SOCK_STREAM | socket.SOCK_NONBLOCK | socket.SOCK_CLOEXEC)
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        self.sock.bind(self.path)
        os.chmod(self.path, 0o600)
        self.sock.listen(16)
        self.inode = os.stat(self.path).st_ino
        self.watch = GLib.unix_fd_add_full(GLib.PRIORITY_HIGH, self.sock.fileno(),
                                           GLib.IOCondition.IN, self._accept)

    def _accept(self, _fd, _cond):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:  # BlockingIOError: all taken
                break
            creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            if struct.unpack("3i", creds)[1] != os.getuid():
                conn.close()
                continue
            conn.setblocking(False)
            Request(self.app, conn)
        return GLib.SOURCE_CONTINUE

    def close(self):
        GLib.source_remove(self.watch)
        self.sock.close()
        try:
            if os.stat(self.path).st_ino == self.inode:
                os.unlink(self.path)
        except OSError:
            pass


class Launcher(Gtk.Application):
    RELOAD_DELAY_MS = 250  # a package install changes many entries at once

    def __init__(self, hidden):
        super().__init__(application_id=APP_ID)
        self._hidden = hidden  # --daemon: the first activation doesn't show
        self._t0 = os.environ.pop("LAUNCHER_T0", None)  # cold start: trace the first show
        self._reload_id = 0
        self.picker = self.server = self.usage = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()  # hidden between shows
        appdb.child_environment()
        install_css(render_css(BASE_CSS) + load_css(os.path.join(_DIR, "style.css")))
        self.usage = appdb.Usage()
        self.picker = Picker(self)
        self._reload()
        # Emits once per change, and again only after the next get_all()
        self._monitor = Gio.AppInfoMonitor.get()
        self._monitor.connect("changed", self._apps_changed)
        self.server = Server(self)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.quit)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.quit)

    def do_activate(self):
        # A launch that lost the race to start the instance lands here too
        t0, self._t0 = self._t0, None
        if self._hidden:
            self._hidden = False
            return
        self.toggle(t0)

    def do_shutdown(self):
        if self.server:
            self.server.close()
        Gtk.Application.do_shutdown(self)

    def toggle(self, t0=None):
        self.picker.toggle(self.usage, t0)

    def _apps_changed(self, _monitor):
        if self._reload_id:
            GLib.source_remove(self._reload_id)
        self._reload_id = GLib.timeout_add(self.RELOAD_DELAY_MS, self._reload)

    def _reload(self):
        self._reload_id = 0
        self.picker.set_apps(appdb.load_apps())
        return GLib.SOURCE_REMOVE

    def launch(self, app):
        context = Gdk.Display.get_default().get_app_launch_context()
        error = appdb.launch(app.info, context)
        if error:
            appdb.notify_error(f"Couldn't launch {app.name}", error)
        else:
            self.usage.bump(app.id)
        return GLib.SOURCE_REMOVE


class DmenuOnce(Gtk.Application):
    """dmenu with no instance running: this process shows the picker, prints
    the pick and exits."""

    def __init__(self, lines, prompt, after_tab):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.lines, self.prompt, self.after_tab = lines, prompt, after_tab
        self.status = 1
        self.picker = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        install_css(render_css(BASE_CSS) + load_css(os.path.join(_DIR, "style.css")))
        self.picker = Picker(self)

    def do_activate(self):
        self.picker.show_dmenu(display_lines(self.lines, self.after_tab), self.prompt, self._picked,
                               os.environ.get("LAUNCHER_T0"))

    def _picked(self, index):
        if index is not None:
            sys.stdout.buffer.write(self.lines[index] + b"\n")
            sys.stdout.flush()
            self.status = 0
        self.quit()


def run_resident(hidden):
    app = Launcher(hidden)
    if hidden:
        app.register(None)
        if app.get_is_remote():
            return 0  # already running (its socket was not where we looked)
    return app.run([sys.argv[0]])


def run_dmenu_once(prompt, after_tab):
    lines = protocol.split_lines(sys.stdin.buffer.read())
    app = DmenuOnce(lines, prompt, after_tab)
    app.run([sys.argv[0]])
    return app.status
