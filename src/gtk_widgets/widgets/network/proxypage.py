"""Proxy rules page: SOCKS5 proxies (paste to import, check, Block QUIC,
delete), per-app rules (running-process picker or manual name), the exit for
everything else and the kill switch. Edits save to the state file at once;
while Proxy rules is on, an Apply bar restarts sing-box with them."""

import re
from collections.abc import Callable
from typing import Literal, Protocol, override

from gi.repository import GLib, Pango

from gtk_widgets.lib.ui.background import in_background
from gtk_widgets.lib.ui.copy_label import copyable
from gtk_widgets.lib.ui.widget_base import Gtk, VScroller
from gtk_widgets.widgets.network import proxy as px
from gtk_widgets.widgets.network import socks5
from gtk_widgets.widgets.network.editor import Choice, edit_section, toggle
from gtk_widgets.widgets.network.nmutil import ICON
from gtk_widgets.widgets.network.parse import Check, Proxy, Rule, State
from gtk_widgets.widgets.network.ui import (
    KeyedList,
    KeyedRow,
    button,
    error_label,
    glyph_button,
    hbox,
    label,
    vbox,
)

# a proxy's check: the last result, "running" while one runs, None if never
type CheckState = Check | Literal["running"] | None
type Exits = list[tuple[str, str]]  # [(exit, label)] for an exit dropdown
MAX_SHOWN_ERRORS = 5  # pasted lines whose errors the form lists
MAX_APP_NAME_BYTES = 255  # a file name's limit
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class ProxyHost(Protocol):
    """What the page needs of the popup."""

    @property
    def proxy_state(self) -> State: ...

    @property
    def proxy_watch(self) -> px.ServiceWatch | None: ...

    def queue_sync(self) -> None: ...


def check_line(res: CheckState) -> tuple[str, str | None]:
    """(text, css class) for a proxy's last check."""
    if res is None:
        return "not checked", None
    if res == "running":
        return "checking…", None
    if not res.ok:
        return f"{ICON['cross']} {res.error}", "net-status-err"
    parts = [f"{ICON['check']} {res.latency_ms} ms"]
    if res.ip:
        parts.append(res.ip)
    if res.country:
        parts.append(res.country)
    return " · ".join(parts), "net-status-ok"


def udp_badge(res: CheckState) -> tuple[str, str | None, str | None]:
    """(text, css class, tooltip) for a proxy's UDP check."""
    if not isinstance(res, Check) or not res.ok or res.udp is None:
        return "", None, None
    if res.udp:
        return (
            f"UDP {ICON['check']}",
            "net-udp-ok",
            f"UDP works ({res.udp_ms} ms round trip)",
        )
    return (
        f"UDP {ICON['cross']}",
        "net-udp-bad",
        (
            f"{res.udp_error}: QUIC and UDP apps fail "
            "through this proxy; turn on Block QUIC so browsers use TCP at once"
        ),
    )


def _section(title: str, *buttons: Gtk.Widget) -> Gtk.Box:
    """An edit_section with buttons beside its title."""
    sec = edit_section(title)
    head = sec.get_first_child()
    if head is None:
        raise RuntimeError("edit_section() has no title")
    head.set_hexpand(True)
    sec.remove(head)
    line = hbox(4)
    line.append(head)
    for b in buttons:
        line.append(b)
    sec.append(line)
    return sec


class ProxyRow(KeyedRow[tuple[Proxy, CheckState]]):
    """Two lines: id and address with check/delete, then the last check,
    UDP and Block QUIC."""

    def __init__(self, page: ProxyPage, pid: str) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.add_css_class("net-row")
        self.page, self.pid = page, pid
        top = hbox(8)
        self.title = label("", "net-row-title", hexpand=True, ellipsize=True)
        top.append(self.title)
        self.stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.NONE, valign=Gtk.Align.CENTER
        )
        actions = hbox(2)
        self.check_btn = glyph_button(
            ICON["rescan"],
            "Check: login, exit IP, latency, UDP",
            lambda: page.check(pid),
        )
        actions.append(self.check_btn)
        actions.append(
            glyph_button(
                ICON["delete"],
                "Delete",
                lambda: self.stack.set_visible_child_name("confirm"),
                "net-delete-btn",
            )
        )
        confirm = hbox(4)
        confirm.append(label("Delete?", "net-confirm"))
        confirm.append(
            button("Delete", "net-btn-danger", on_click=lambda: page.delete_proxy(pid))
        )
        confirm.append(
            button(
                "Keep", on_click=lambda: self.stack.set_visible_child_name("actions")
            )
        )
        _ = self.stack.add_named(actions, "actions")
        _ = self.stack.add_named(confirm, "confirm")
        top.append(self.stack)
        self.append(top)
        line = hbox(8)
        self.subtitle = label("", "net-row-subtitle", hexpand=True, ellipsize=True)
        self.udp = label("", "net-row-subtitle")
        line.append(self.subtitle)
        line.append(self.udp)
        self.quic = Gtk.CheckButton(label="Block QUIC", valign=Gtk.Align.CENTER)
        self.quic.set_tooltip_text(
            "Reject QUIC (UDP 443) for apps on this proxy, so browsers "
            "fall back to TCP at once. For proxies without working UDP."
        )
        self._quic_handler = self.quic.connect("toggled", self._on_quic)
        line.append(self.quic)
        self.append(line)

    @override
    def update(self, data: tuple[Proxy, CheckState]) -> None:
        p, res = data
        check = res if isinstance(res, Check) else None
        self.title.set_text(f"{p.id} · {p.host}:{p.port}")
        self.title.set_tooltip_text(
            f"{p.host}:{p.port}, "
            + (f"user {p.username}" if p.username else "no login")
        )
        text, cls = check_line(res)
        failed = cls == "net-status-err"
        self.subtitle.set_text(text)
        _ = copyable(
            self.subtitle,
            on=failed,
            copy_text=check.error if check and failed else None,
        )
        self.subtitle.set_tooltip_text(text + ("\nClick to copy" if failed else ""))
        self.subtitle.set_css_classes(["net-row-subtitle"] + ([cls] if cls else []))
        badge, bcls, tip = udp_badge(res)
        bad = bcls == "net-udp-bad"
        self.udp.set_text(badge)
        _ = copyable(
            self.udp, on=bad, copy_text=check.udp_error if check and bad else None
        )
        self.udp.set_tooltip_text(tip and tip + ("\nClick to copy" if bad else ""))
        self.udp.set_css_classes(["net-row-subtitle"] + ([bcls] if bcls else []))
        self.check_btn.set_sensitive(res != "running")
        self.quic.handler_block(self._quic_handler)
        self.quic.set_active(p.block_quic)
        self.quic.handler_unblock(self._quic_handler)

    def _on_quic(self, btn: Gtk.CheckButton) -> None:
        self.page.set_block_quic(self.pid, on=btn.get_active())


class RuleRow(KeyedRow[tuple[str, Exits, str | None]]):
    """An app rule: its exit dropdown; data is (exit, exits, executable path)."""

    def __init__(self, page: ProxyPage, app: str) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.add_css_class("net-row")
        self.page, self.app = page, app
        self.name = label(app, "net-row-title", hexpand=True, ellipsize=True)
        self.append(self.name)
        self.exit: Choice[str] | None = None
        self.box = hbox(0)
        self.append(self.box)
        self.append(
            glyph_button(
                ICON["delete"],
                "Remove rule",
                lambda: page.remove_rule(app),
                "net-delete-btn",
            )
        )
        self._options: Exits | None = None

    @override
    def update(self, data: tuple[str, Exits, str | None]) -> None:
        exit_, options, path = data
        self.name.set_tooltip_text(path or "not running now")
        choice = self.exit
        if choice is None or options != self._options:
            if choice is not None:
                self.box.remove(choice)
            choice = Choice(options, self._exit_changed)
            choice.set_hexpand(False)
            self.exit = choice
            self.box.append(choice)
            self._options = options
        if choice.value() != exit_:
            choice.set_value(exit_)

    def _exit_changed(self) -> None:
        if self.exit is not None:
            self.page.set_rule(self.app, self.exit.value())


class _AppRow(Gtk.ListBoxRow):
    def __init__(self, app: str) -> None:
        super().__init__()
        self.app = app


class AppPicker(Gtk.Box):
    """Running programs by executable name (the name sing-box matches), apps
    with a window first; typing filters, Add takes the typed name as is."""

    def __init__(
        self, on_pick: Callable[[str], None], on_cancel: Callable[[], None]
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("net-form")
        self.on_pick = on_pick
        self.append(label("Add app", "net-form-title"))
        hint = label(
            "Executable names, as the kernel reports them: Telegram may be "
            "“Telegram”, Steam's web traffic comes from “steamwebhelper”.",
            "net-edit-hint",
        )
        hint.set_wrap(True)
        hint.set_max_width_chars(48)
        self.append(hint)
        row = hbox(4)
        self.search = Gtk.SearchEntry(
            hexpand=True, placeholder_text="Filter or type a name"
        )
        self.search.add_css_class("net-entry")
        _ = self.search.connect("search-changed", self._search_changed)
        _ = self.search.connect("activate", self._search_activated)
        row.append(self.search)
        row.append(button("Add", "net-btn-accent", on_click=self._add_typed))
        self.append(row)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class("net-app-list")
        self.list.set_filter_func(self._filter)
        _ = self.list.connect("row-activated", self._activated)
        scroller = VScroller(200)
        scroller.set_child(self.list)
        self.append(scroller)
        buttons = hbox(4)
        buttons.set_halign(Gtk.Align.END)
        buttons.append(button("Cancel", on_click=on_cancel))
        self.append(buttons)
        self.set_visible(False)

    def _search_changed(self, _entry: Gtk.SearchEntry) -> None:
        self.list.invalidate_filter()

    def _search_activated(self, _entry: Gtk.SearchEntry) -> None:
        self._add_typed()

    def _activated(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        if isinstance(row, _AppRow):
            self.on_pick(row.app)

    def open(self, taken: set[str]) -> None:
        self.list.remove_all()
        apps, windows = px.running_apps(), px.window_apps()
        names = sorted(
            (n for n in apps if n not in taken),
            key=lambda n: (n not in windows, n.lower()),
        )
        for name in names:
            r = _AppRow(name)
            line = hbox(8)
            line.append(label(name, "net-app-name", hexpand=True, ellipsize=True))
            path = label(apps[name], "net-edit-hint")
            path.set_ellipsize(Pango.EllipsizeMode.START)
            path.set_max_width_chars(26)
            line.append(path)
            if name in windows:
                line.append(label("window", "net-app-window"))
            r.set_child(line)
            r.set_tooltip_text(apps[name])
            self.list.append(r)
        self.search.set_text("")
        self.set_visible(True)
        _ = self.search.grab_focus()

    def _filter(self, row: Gtk.ListBoxRow) -> bool:
        text = self.search.get_text().strip().lower()
        return not text or (isinstance(row, _AppRow) and text in row.app.lower())

    def _add_typed(self) -> None:
        name = self.search.get_text().strip()
        if name:
            self.on_pick(name)


class PasteForm(Gtk.Box):
    def __init__(
        self, on_add: Callable[[str], None], on_cancel: Callable[[], None]
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("net-form")
        self.append(label("Paste proxies", "net-form-title"))
        hint = label(
            "One per line: host:port:user:pass (also host:port, "
            "user:pass@host:port, socks5://…). SOCKS5 only.",
            "net-edit-hint",
        )
        hint.set_wrap(True)
        hint.set_max_width_chars(48)
        self.append(hint)
        self.view = Gtk.TextView(
            monospace=True,
            wrap_mode=Gtk.WrapMode.CHAR,
            accepts_tab=False,
            height_request=72,
        )
        self.view.add_css_class("net-paste")
        self.append(self.view)
        self.error = error_label()
        self.append(self.error)
        buttons = hbox(4)
        buttons.set_halign(Gtk.Align.END)
        buttons.append(button("Cancel", on_click=on_cancel))
        buttons.append(
            button("Add", "net-btn-accent", on_click=lambda: on_add(self.text()))
        )
        self.append(buttons)
        self.set_visible(False)

    def text(self) -> str:
        buf = self.view.get_buffer()
        return buf.get_text(
            buf.get_start_iter(), buf.get_end_iter(), include_hidden_chars=False
        )

    def open(self) -> None:
        self.view.get_buffer().set_text("")
        self.show_error(None)
        self.set_visible(True)
        _ = self.view.grab_focus()

    def show_error(self, text: str | None) -> None:
        self.error.set_text(text or "")
        self.error.set_visible(bool(text))


class ProxyPage(Gtk.Box):
    def __init__(self, app: ProxyHost, on_back: Callable[[], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.app = app
        header = hbox(6)
        header.append(glyph_button(ICON["back"], "Back", on_back))
        header.append(label("Proxy rules", "net-title", hexpand=True))
        self.page_state = label("", "net-vpn-state")
        header.append(self.page_state)
        self.append(header)

        body = vbox(10)
        scroller = VScroller(560)
        scroller.set_child(body)
        self.append(scroller)

        self.check_all_btn = button("Check all", on_click=self.check_all)
        sec = _section(
            "Proxies", self.check_all_btn, button("Paste…", on_click=self._open_paste)
        )
        self.paste = PasteForm(self._add_pasted, lambda: self.paste.set_visible(False))
        sec.append(self.paste)
        self.no_proxies = label(
            "No proxies yet: paste your provider's host:port:user:pass lines.",
            "net-empty",
        )
        self.no_proxies.set_wrap(True)
        sec.append(self.no_proxies)
        self.proxies: KeyedList[str, tuple[Proxy, CheckState]] = KeyedList(
            self._proxy_row
        )
        sec.append(self.proxies)
        body.append(sec)

        self.add_app_btn = button("Add app…", on_click=self._open_picker)
        sec = _section("Apps", self.add_app_btn)
        self.picker = AppPicker(self._pick, lambda: self.picker.set_visible(False))
        sec.append(self.picker)
        self.rules: KeyedList[str, tuple[str, Exits, str | None]] = KeyedList(
            self._rule_row
        )
        sec.append(self.rules)
        other = hbox(8)
        other.add_css_class("net-row")
        other.append(label("Everything else", "net-row-title", hexpand=True))
        self.default_box = hbox(0)
        other.append(self.default_box)
        sec.append(other)
        lan = label("LAN and private addresses always go direct.", "net-edit-hint")
        sec.append(lan)
        body.append(sec)
        self.default: Choice[str] | None = None
        self._default_options: Exits | None = None

        self.kill = toggle(self._on_kill)
        body.append(self._kill_section())

        self._build_footer()
        self._running: dict[str, bool] = {}  # pid -> True while a check runs
        self._applying = False
        self._syncing = False

    def _build_footer(self) -> None:
        """The message line and the Apply bar."""
        self.msg = label("", "net-edit-msg")
        self.msg.set_wrap(True)
        self.msg.set_visible(False)
        self.append(self.msg)
        self.apply_bar = hbox(8, "net-inet")
        self.apply_msg = label(
            "Changes are saved but not applied", "net-inet-msg", hexpand=True
        )
        self.apply_msg.set_wrap(True)
        self.apply_bar.append(self.apply_msg)
        self.apply_btn = button(
            "Apply",
            "net-btn-accent",
            tooltip="Restart sing-box with these rules",
            on_click=self._apply,
        )
        self.apply_bar.append(self.apply_btn)
        self.apply_bar.set_visible(False)
        self.append(self.apply_bar)

    def _proxy_row(self, pid: str) -> ProxyRow:
        return ProxyRow(self, pid)

    def _rule_row(self, app: str) -> RuleRow:
        return RuleRow(self, app)

    def _kill_section(self) -> Gtk.Box:
        sec = edit_section("Kill switch")
        row = hbox(8)
        hint = label(
            "If sing-box stops while Proxy rules is on, block all internet traffic "
            "(the LAN still works) until you pick another exit. It cannot tell apps "
            "apart once sing-box is gone, so direct apps are blocked too.",
            "net-edit-hint",
            hexpand=True,
        )
        hint.set_wrap(True)
        hint.set_max_width_chars(44)
        row.append(hint)
        row.append(self.kill)
        sec.append(row)
        return sec

    @property
    def state(self) -> State:
        return self.app.proxy_state

    # --- sync ---

    def sync(self) -> None:
        st, watch = self.state, self.app.proxy_watch
        self._syncing = True
        self.no_proxies.set_visible(not st.proxies)
        self.proxies.sync(
            [
                (
                    p.id,
                    (
                        p,
                        "running" if self._running.get(p.id) else st.checks.get(p.id),
                    ),
                )
                for p in st.proxies
            ]
        )
        self.check_all_btn.set_visible(bool(st.proxies))
        options = [(px.DIRECT, "direct")] + [
            (p.id, px.exit_label(st, p.id)) for p in st.proxies
        ]
        running = px.running_apps() if st.rules else {}
        self.rules.sync(
            [(r.app, (r.exit, options, running.get(r.app))) for r in st.rules]
        )
        default = self.default
        if default is None or options != self._default_options:
            if default is not None:
                self.default_box.remove(default)
            default = Choice(options, self._on_default)
            default.set_hexpand(False)
            self.default = default
            self.default_box.append(default)
            self._default_options = options
        if default.value() != st.default:
            default.set_value(st.default)
        self.kill.set_active(bool(st.kill_switch))
        on = watch is not None and (watch.active or watch.starting)
        self.page_state.set_text(
            f"{ICON['check']} on"
            if watch and watch.active
            else "starting…"
            if on
            else "off"
        )
        self.page_state.set_css_classes(
            ["net-vpn-state"] + (["net-vpn-on"] if watch and watch.active else [])
        )
        pending = on and px.pending_changes(st)
        self.apply_bar.set_visible(pending or self._applying)
        self.apply_btn.set_sensitive(not self._applying)
        self._syncing = False

    def show_msg(
        self, text: str | None, *, error: bool = False, ok: bool = False
    ) -> None:
        self.msg.set_text(text or "")
        self.msg.set_visible(bool(text))
        self.msg.set_css_classes(
            ["net-edit-msg"]
            + (["net-status-err"] if error else [])
            + (["net-status-ok"] if ok else [])
        )
        _ = copyable(self.msg, on=error)

    def changed(self) -> None:
        try:
            px.save_state(self.state)
        except OSError as e:
            self.show_msg(f"Cannot save {px.STATE_PATH}: {e.strerror}", error=True)
        self.app.queue_sync()

    # --- proxies ---

    def _open_paste(self) -> None:
        self.picker.set_visible(False)
        self.paste.open()

    def _add_pasted(self, text: str) -> None:
        added, errors = px.import_lines(self.state, text)
        if errors:
            self.paste.show_error(
                "\n".join(f"Line {n}: {e}" for n, e in errors[:MAX_SHOWN_ERRORS])
                + ("\n…" if len(errors) > MAX_SHOWN_ERRORS else "")
            )
        else:
            self.paste.set_visible(False)
        if added:
            self.show_msg(
                f"Added {added} prox{'ies' if added != 1 else 'y'}: checking…", ok=True
            )
            self.changed()
            for p in self.state.proxies[-added:]:
                self.check(p.id)
        elif not errors:
            self.show_msg("Nothing new: those proxies are already in the list")
            self.changed()

    def delete_proxy(self, pid: str) -> None:
        used = [r.app for r in self.state.rules if r.exit == pid]
        px.remove_proxy(self.state, pid)
        self.show_msg(
            f"Deleted {pid}"
            + (f"; removed the rules for {', '.join(used)}" if used else "")
        )
        self.changed()

    def set_block_quic(self, pid: str, *, on: bool) -> None:
        p = px.proxy_by_id(self.state, pid)
        if p and p.block_quic != on:
            p.block_quic = on
            self.changed()

    def check_all(self) -> None:
        for p in self.state.proxies:
            self.check(p.id)

    def check(self, pid: str) -> None:
        p = px.proxy_by_id(self.state, pid)
        if p is None or self._running.get(pid):
            return
        self._running[pid] = True
        self.app.queue_sync()
        args = (p.host, p.port, p.username, p.password)

        def work() -> None:
            res = socks5.check(*args)

            def checked() -> bool:
                return self._checked(pid, args, res)

            _ = GLib.idle_add(checked)

        def bug(text: str) -> None:
            _ = self._running.pop(pid, None)
            self.show_msg(text, error=True)
            self.app.queue_sync()

        in_background(work, bug)

    def _checked(self, pid: str, args: tuple[str, int, str, str], res: Check) -> bool:
        _ = self._running.pop(pid, None)
        p = px.proxy_by_id(self.state, pid)
        if p is not None and (p.host, p.port, p.username, p.password) == args:
            self.state.checks[pid] = res
            self.changed()
        self.app.queue_sync()
        return GLib.SOURCE_REMOVE

    # --- rules ---

    def _open_picker(self) -> None:
        if not self.state.proxies:
            self.show_msg("Paste a proxy first", error=True)
            return
        self.paste.set_visible(False)
        self.picker.open({r.app for r in self.state.rules})

    def _pick(self, app: str) -> None:
        app = app.strip()
        problem = _app_problem(app)
        if problem:
            self.show_msg(problem, error=True)
            return
        if any(r.app == app for r in self.state.rules):
            self.show_msg(f"{app} already has a rule", error=True)
            return
        self.picker.set_visible(False)
        exit_ = self.state.proxies[0].id
        self.state.rules.append(Rule(app, exit_))
        self.show_msg(f"{app} → {exit_}")
        self.changed()

    def set_rule(self, app: str, exit_: str) -> None:
        if self._syncing:
            return
        for r in self.state.rules:
            if r.app == app and r.exit != exit_:
                r.exit = exit_
                self.changed()

    def remove_rule(self, app: str) -> None:
        self.state.rules = [r for r in self.state.rules if r.app != app]
        self.changed()

    def _on_default(self) -> None:
        if self._syncing or self.default is None:
            return
        if self.state.default != self.default.value():
            self.state.default = self.default.value()
            self.changed()

    def _on_kill(self) -> None:
        if self._syncing:
            return
        on = self.kill.get_active()
        if bool(self.state.kill_switch) != on:
            self.state.kill_switch = on
            self.changed()

    # --- apply ---

    def _apply(self) -> None:
        problem = px.usable_problem(self.state)
        if problem:
            self.show_msg(f"{problem}, or pick Off on the main page", error=True)
            return
        self._applying = True
        self.apply_msg.set_text("Restarting sing-box…")
        self.app.queue_sync()

        def done(err: str | None) -> None:
            self._applying = False
            self.apply_msg.set_text("Changes are saved but not applied")
            if err:
                self.show_msg(f"Not applied: {err}", error=True)
            else:
                self.show_msg(f"Applied: {px.summary(self.state)}", ok=True)
            self.app.queue_sync()

        px.apply(self.state, done)


def _app_problem(app: str) -> str | None:
    """Why `app` can't be an executable name, or None."""
    if (
        not app
        or app in {".", ".."}
        or "/" in app
        or len(app.encode()) > MAX_APP_NAME_BYTES
        or _CONTROL_RE.search(app)
    ):
        return f"“{app}” is not an executable name"
    return None
