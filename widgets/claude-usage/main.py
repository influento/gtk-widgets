#!/usr/bin/env python3
"""Claude usage popup — GTK4 widget showing subscription utilization with progress bars."""

import json, os, subprocess, sys, urllib.request
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib.widget_base import Gtk, WidgetPopup, load_css

from datetime import date, datetime, timezone
from pathlib import Path

CSS = load_css(os.path.join(_DIR, "style.css"))

CACHE_PATH = Path.home() / ".claude" / "subscription_cache.json"


def fetch_data(force=False):
    """Call claude-usage --json and return parsed data."""
    cmd = [os.path.join(_DIR, "status"), "--json"]
    if force:
        cmd.append("--refresh")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)


def format_reset(iso_str):
    """Format reset as absolute day/time + relative duration."""
    reset = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    local = reset.astimezone()
    absolute = local.strftime("%a %-I:%M %p")
    now = datetime.now(timezone.utc)
    delta = reset - now
    total_minutes = int(delta.total_seconds() / 60)
    if total_minutes < 0:
        return "resets now"
    total_hours, minutes = divmod(total_minutes, 60)
    if total_hours >= 24:
        days, hours = divmod(total_hours, 24)
        relative = f"{days}d {hours}h"
    elif total_hours > 0:
        relative = f"{total_hours}h {minutes}m"
    else:
        relative = f"{minutes}m"
    return f"resets {absolute} ({relative})"


def format_charge_date(date_str):
    """Format charge date as absolute + relative."""
    target = datetime.strptime(date_str, "%Y-%m-%d")
    absolute = target.strftime("%b %-d")
    target_utc = target.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = target_utc - now
    total_hours = int(delta.total_seconds() / 3600)
    if total_hours < 0:
        return f"{absolute} (now)"
    if total_hours >= 24:
        days, hours = divmod(total_hours, 24)
        return f"{absolute} ({days}d {hours}h)"
    minutes = int((delta.total_seconds() % 3600) / 60)
    return f"{absolute} ({total_hours}h {minutes}m)"


def classify(pct):
    """Return CSS class based on utilization percentage."""
    if pct > 95:
        return "high"
    if pct >= 80:
        return "medium"
    return "low"


def has_valid_cache():
    """Check if cached charge date exists and is in the future."""
    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
        charge_date = cache.get("next_charge_date")
        if charge_date and datetime.strptime(charge_date, "%Y-%m-%d").date() >= date.today():
            return True
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
        pass
    return False


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


class ClaudeUsagePopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.claude-usage")

    def build_ui(self):
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._container.add_css_class("usage-container")
        self._build_content()
        return self._container

    def _build_content(self, force=False):
        """Build or rebuild all content in the container."""
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

        # Fetch data
        try:
            data = fetch_data(force=force)
            if "error" in data:
                raise RuntimeError(data["error"])
            self._build_window_row(self._container, "5-hour", data["five_hour"])
            self._build_window_row(self._container, "7-day", data["seven_day"])
            sonnet = data.get("seven_day_sonnet")
            if sonnet and sonnet.get("utilization") is not None and sonnet.get("resets_at"):
                self._build_window_row(self._container, "7-day sonnet", sonnet)
            self._build_charge_section(self._container, data)
        except Exception as e:
            error_label = Gtk.Label(label=f"Failed to fetch usage data: {e}")
            error_label.add_css_class("usage-error")
            error_label.set_wrap(True)
            error_label.set_max_width_chars(40)
            self._container.append(error_label)

    def _build_window_row(self, container, name, window_data):
        """Build a labeled progress bar row for one usage window."""
        pct = window_data["utilization"]
        level = classify(pct)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        name_label = Gtk.Label(label=name)
        name_label.add_css_class("usage-window-label")
        name_label.set_hexpand(True)
        name_label.set_halign(Gtk.Align.START)
        header.append(name_label)

        pct_label = Gtk.Label(label=f"{round(pct)}%")
        pct_label.add_css_class("usage-pct")
        pct_label.add_css_class(f"pct-{level}")
        header.append(pct_label)

        container.append(header)

        bar = Gtk.ProgressBar()
        bar.set_fraction(min(pct / 100.0, 1.0))
        bar.add_css_class(level)
        container.append(bar)

        reset_label = Gtk.Label(label=format_reset(window_data["resets_at"]))
        reset_label.add_css_class("usage-reset")
        reset_label.set_halign(Gtk.Align.START)
        container.append(reset_label)

    def _build_charge_section(self, container, data):
        """Show charge date if cached, or session key input if not."""
        separator = Gtk.Separator()
        separator.add_css_class("usage-separator")
        container.append(separator)

        charge_date = data.get("next_charge_date")
        if charge_date:
            label = Gtk.Label(label=f"next charge: {format_charge_date(charge_date)}")
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

        submit_btn = Gtk.Button(label="save")
        submit_btn.add_css_class("session-button")
        submit_btn.connect("clicked", lambda _: self._on_submit())
        input_row.append(submit_btn)

        container.append(input_row)

        self._status_label = Gtk.Label()
        self._status_label.set_halign(Gtk.Align.START)
        container.append(self._status_label)

    def _on_submit(self):
        """Fetch subscription details and cache the result."""
        session_key = self._session_entry.get_text().strip()
        if not session_key:
            return

        try:
            org_uuid = get_org_uuid()
            try:
                sub = fetch_subscription(session_key, org_uuid)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    org_uuid = get_org_uuid(force_refresh=True)
                    sub = fetch_subscription(session_key, org_uuid)
                else:
                    raise
            charge_date = sub.get("next_charge_date")
            if not charge_date:
                raise ValueError("no next_charge_date in response")

            cache = {"next_charge_date": charge_date, "org_uuid": org_uuid}
            with open(CACHE_PATH, "w") as f:
                json.dump(cache, f)

            self._status_label.set_text(f"saved — next charge: {format_charge_date(charge_date)}")
            self._status_label.remove_css_class("session-status-err")
            self._status_label.add_css_class("session-status")
            self._status_label.add_css_class("session-status-ok")
            self._session_entry.set_text("")
        except Exception as e:
            self._status_label.set_text(f"failed: {e}")
            self._status_label.remove_css_class("session-status-ok")
            self._status_label.add_css_class("session-status")
            self._status_label.add_css_class("session-status-err")


if __name__ == "__main__":
    ClaudeUsagePopup.CSS = CSS
    ClaudeUsagePopup().run()
