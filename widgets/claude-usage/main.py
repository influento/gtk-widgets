#!/usr/bin/env python3
"""Claude usage popup — GTK4 widget showing subscription utilization with progress bars."""

import json, os, subprocess, sys, threading, urllib.error, urllib.request
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))
sys.path.insert(0, _DIR)

from lib.copy_label import copyable
from lib.widget_base import Gtk, WidgetPopup

from gi.repository import GLib

from pathlib import Path

from usage import describe_charge_date, describe_reset, severity  # noqa: E402

CACHE_PATH = Path.home() / ".claude" / "subscription_cache.json"


def fetch_data(force=False):
    """Call claude-usage --json and return parsed data."""
    cmd = [os.path.join(_DIR, "status"), "--json"]
    if force:
        cmd.append("--refresh")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)


def fetch_subscription(session_key, org_uuid):
    """Fetch subscription details using session key cookie."""
    url = f"https://api.anthropic.com/api/organizations/{org_uuid}/subscription_details"
    req = urllib.request.Request(url, headers={
        "Content-Type": "application/json",
        "Cookie": f"sessionKey={session_key}",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get_org_uuid(force_refresh=False):
    """Get org UUID from cache or OAuth profile."""
    if not force_refresh:
        try:
            with open(CACHE_PATH) as f:
                cached = json.load(f).get("org_uuid")
            if cached:
                return cached
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    creds_path = Path.home() / ".claude" / ".credentials.json"
    with open(creds_path) as f:
        token = json.load(f)["claudeAiOauth"]["accessToken"]
    req = urllib.request.Request(
        "https://api.anthropic.com/api/oauth/profile",
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["organization"]["uuid"]


def save_subscription(session_key):
    """Fetch next_charge_date with the session key, cache it, and return it."""
    org_uuid = get_org_uuid()
    try:
        sub = fetch_subscription(session_key, org_uuid)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        org_uuid = get_org_uuid(force_refresh=True)
        sub = fetch_subscription(session_key, org_uuid)
    charge_date = sub.get("next_charge_date")
    if not charge_date:
        raise ValueError("no next_charge_date in response")
    with open(CACHE_PATH, "w") as f:
        json.dump({"next_charge_date": charge_date, "org_uuid": org_uuid}, f)
    return charge_date


class ClaudeUsagePopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.claude-usage")
        self._generation = 0  # bumps on every rebuild so stale fetches are dropped

    def build_ui(self):
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._container.add_css_class("usage-container")
        self._build_content()
        return self._container

    def _build_content(self, force=False):
        """Rebuild the title row, then fetch usage data off the main thread."""
        while child := self._container.get_first_child():
            self._container.remove(child)

        # Title row with refresh button
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="Claude Usage")
        title.add_css_class("usage-title")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        title_row.append(title)

        refresh_btn = Gtk.Button(label="󰑓")
        refresh_btn.add_css_class("refresh-button")
        refresh_btn.set_tooltip_text("Refresh usage data")
        refresh_btn.connect("clicked", lambda _: self._build_content(force=True))
        title_row.append(refresh_btn)

        self._container.append(title_row)

        loading = Gtk.Label(label="loading…")
        loading.add_css_class("usage-loading")
        loading.set_halign(Gtk.Align.START)
        self._container.append(loading)

        self._generation += 1
        generation = self._generation

        def worker():
            try:
                data = fetch_data(force=force)
            except Exception as e:
                data = {"error": str(e)}
            GLib.idle_add(self._render_data, generation, loading, data)
        threading.Thread(target=worker, daemon=True).start()

    def _render_data(self, generation, loading, data):
        """Main thread: replace the loading label with the fetched content."""
        if generation != self._generation:
            return GLib.SOURCE_REMOVE  # a newer rebuild already replaced this view
        self._container.remove(loading)
        try:
            if "error" in data:
                raise RuntimeError(data["error"])
            windows = data.get("windows") or []
            if not windows:
                raise RuntimeError("no usage windows in response")
            for window in windows:
                self._build_window_row(self._container, window)
            self._build_spend_row(self._container, data.get("spend"))
            self._build_charge_section(self._container, data)
        except Exception as e:
            error_label = Gtk.Label(label=f"Failed to fetch usage data: {e}")
            error_label.add_css_class("usage-error")
            error_label.set_wrap(True)
            error_label.set_max_width_chars(40)
            copyable(error_label)
            self._container.append(error_label)
        return GLib.SOURCE_REMOVE

    def _build_window_row(self, container, window):
        """Build a labeled progress bar row for one usage window."""
        pct = window["percent"]
        level = severity(pct)
        period = "5h" if window["kind"] == "session" else "7d"

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        name_label = Gtk.Label(label=window["label"])
        name_label.add_css_class("usage-window-label")
        name_label.set_halign(Gtk.Align.START)
        header.append(name_label)

        period_label = Gtk.Label(label=period)
        period_label.add_css_class("usage-period")
        period_label.set_hexpand(True)
        period_label.set_halign(Gtk.Align.START)
        header.append(period_label)

        pct_label = Gtk.Label(label=f"{round(pct)}%")
        pct_label.add_css_class("usage-pct")
        pct_label.add_css_class(f"pct-{level}")
        header.append(pct_label)

        container.append(header)

        bar = Gtk.ProgressBar()
        bar.set_fraction(min(pct / 100.0, 1.0))
        bar.add_css_class(level)
        container.append(bar)

        if window.get("resets_at"):
            reset_label = Gtk.Label(label=describe_reset(window["resets_at"]))
            reset_label.add_css_class("usage-reset")
            reset_label.set_halign(Gtk.Align.START)
            container.append(reset_label)

    def _build_spend_row(self, container, spend):
        """Show extra-usage spend when the account has it enabled."""
        if not spend or not spend.get("enabled"):
            return
        used = spend.get("used") or {}
        exponent = used.get("exponent", 2)
        amount = used.get("amount_minor", 0) / (10 ** exponent)
        currency = used.get("currency", "USD")
        text = f"extra usage: {amount:.2f} {currency}"
        limit = spend.get("limit")
        if isinstance(limit, dict) and limit.get("amount_minor") is not None:
            cap = limit["amount_minor"] / (10 ** limit.get("exponent", exponent))
            text += f" / {cap:.2f} {currency}"
        label = Gtk.Label(label=text)
        label.add_css_class("usage-charge-label")
        label.set_halign(Gtk.Align.START)
        container.append(label)

    def _build_charge_section(self, container, data):
        """Show charge date if cached, or session key input if not."""
        separator = Gtk.Separator()
        separator.add_css_class("usage-separator")
        container.append(separator)

        charge_date = data.get("next_charge_date")
        if charge_date:
            label = Gtk.Label(label=f"next charge: {describe_charge_date(charge_date)}")
            label.add_css_class("usage-charge-label")
            label.set_halign(Gtk.Align.START)
            container.append(label)
            return

        hint = Gtk.Label(label="paste session key to fetch billing info")
        hint.add_css_class("session-label")
        hint.set_halign(Gtk.Align.START)
        container.append(hint)

        input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._session_entry = Gtk.Entry()
        self._session_entry.set_placeholder_text("sk-ant-sid02-...")
        self._session_entry.add_css_class("session-entry")
        self._session_entry.set_hexpand(True)
        self._session_entry.set_visibility(False)
        self._session_entry.connect("activate", lambda _: self._on_submit())
        input_row.append(self._session_entry)

        self._submit_btn = Gtk.Button(label="save")
        self._submit_btn.add_css_class("session-button")
        self._submit_btn.connect("clicked", lambda _: self._on_submit())
        input_row.append(self._submit_btn)

        container.append(input_row)

        self._status_label = Gtk.Label()
        self._status_label.set_halign(Gtk.Align.START)
        container.append(self._status_label)

    def _on_submit(self):
        """Fetch subscription details off the main thread and cache the result."""
        session_key = self._session_entry.get_text().strip()
        if not session_key:
            return
        self._session_entry.set_sensitive(False)
        self._submit_btn.set_sensitive(False)
        self._set_session_status("fetching…", None)

        def worker():
            try:
                charge_date = save_subscription(session_key)
            except Exception as e:
                GLib.idle_add(self._on_submit_done, None, str(e))
            else:
                GLib.idle_add(self._on_submit_done, charge_date, None)
        threading.Thread(target=worker, daemon=True).start()

    def _on_submit_done(self, charge_date, error):
        self._session_entry.set_sensitive(True)
        self._submit_btn.set_sensitive(True)
        if error:
            self._set_session_status(f"failed: {error}", "session-status-err")
        else:
            self._set_session_status(
                f"saved — next charge: {describe_charge_date(charge_date)}", "session-status-ok")
            self._session_entry.set_text("")
        return GLib.SOURCE_REMOVE

    def _set_session_status(self, text, css_class):
        self._status_label.set_text(text)
        self._status_label.add_css_class("session-status")
        for cls in ("session-status-ok", "session-status-err"):
            self._status_label.remove_css_class(cls)
        if css_class:
            self._status_label.add_css_class(css_class)
        copyable(self._status_label, css_class == "session-status-err")


if __name__ == "__main__":
    ClaudeUsagePopup().run()
