#!/usr/bin/env python3
"""Claude usage popup — GTK4 widget showing subscription utilization with progress bars."""

import json
import subprocess
from dataclasses import asdict, replace
from typing import override

from gi.repository import GLib

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.lib.paths import module_child
from gtk_widgets.lib.ui.background import in_background
from gtk_widgets.lib.ui.copy_label import copyable
from gtk_widgets.lib.ui.widget_base import Gtk, WidgetPopup
from gtk_widgets.widgets.claude_usage import api, status
from gtk_widgets.widgets.claude_usage.parse import (
    ChargeCache,
    Org,
    Report,
    Spend,
    Window,
    parse_charge_date,
    parse_profile,
    parse_report,
)
from gtk_widgets.widgets.claude_usage.usage import (
    UsageError,
    describe_charge_date,
    describe_reset,
    severity,
)

PLAN_CHECK_TIMEOUT_S = 3  # the plan check runs before the popup renders


def fetch_data(*, force: bool = False) -> Report | UsageError:
    """Call claude-usage --json and return parsed data."""
    cmd, env = module_child(status.__name__)
    cmd.append("--json")
    if force:
        cmd.append("--refresh")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=env, check=False
        )
        data: object = json.loads(result.stdout)
    except (OSError, ValueError) as e:
        return UsageError(str(e))
    match parse_report(data):
        case ParseError() as e:
            return UsageError(str(e))
        case report:
            return report


def fetch_subscription(session_key: str, org_uuid: str) -> str | UsageError:
    """The next charge date, fetched with the session key cookie."""
    return api.get(
        f"/api/organizations/{org_uuid}/subscription_details",
        {"Content-Type": "application/json", "Cookie": f"sessionKey={session_key}"},
        parse_charge_date,
    )


def fetch_profile(timeout: float = 10) -> Org | UsageError:
    """The OAuth profile's organization (uuid, plan)."""
    match api.load_token():
        case UsageError() as e:
            return e
        case token:
            return api.get(
                "/api/oauth/profile", api.oauth_headers(token), parse_profile, timeout
            )


def save_cache(cache: ChargeCache) -> UsageError | None:
    fields = {k: v for k, v in asdict(cache).items() if v is not None}
    try:
        status.SUBSCRIPTION_CACHE.write_text(json.dumps(fields))
    except OSError as e:
        return UsageError(str(e))
    return None


def save_subscription(session_key: str) -> str | UsageError:
    """Fetch next_charge_date with the session key, cache it with the plan, and return it."""
    match fetch_profile():
        case UsageError() as e:
            return e
        case org:
            pass
    match fetch_subscription(session_key, org.uuid):
        case UsageError() as e:
            return e
        case charge_date:
            pass
    return save_cache(ChargeCache(charge_date, org.uuid, org.plan)) or charge_date


def plan_unchanged() -> bool | UsageError:
    """False (and the charge date forgotten) when the plan changed since the date was saved.

    The cached date is rolled forward monthly, which holds only while the billing day
    stays; a plan change can move it, so the session key is asked for again.
    """
    cache = status.load_charge_cache()
    if not cache.next_charge_date:
        return True
    match fetch_profile(timeout=PLAN_CHECK_TIMEOUT_S):
        case UsageError() as e:
            return e
        case org:
            plan = org.plan
    if cache.plan is None:  # saved before plans were recorded: take the current one
        return save_cache(replace(cache, plan=plan)) or True
    if cache.plan == plan:
        return True
    return save_cache(replace(cache, next_charge_date=None, plan=None)) or False


class ClaudeUsagePopup(WidgetPopup):
    def __init__(self) -> None:
        super().__init__(application_id="dev.dotfiles.claude-usage")
        self._generation = 0  # bumps on every rebuild so stale fetches are dropped

    @override
    def build_ui(self) -> Gtk.Widget:
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._container.add_css_class("usage-container")
        self._build_content()
        return self._container

    def _build_content(self, *, force: bool = False) -> None:
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
        refresh_btn.connect("clicked", self._on_refresh)
        title_row.append(refresh_btn)

        self._container.append(title_row)

        loading = Gtk.Label(label="loading…")
        loading.add_css_class("usage-loading")
        loading.set_halign(Gtk.Align.START)
        self._container.append(loading)

        self._generation += 1
        generation = self._generation

        def worker() -> None:
            result = fetch_data(force=force)
            # offline or no credentials (a UsageError): keep the date
            if (
                isinstance(result, Report)
                and result.next_charge_date
                and plan_unchanged() is False
            ):
                result = replace(result, next_charge_date=None, plan_changed=True)
            GLib.idle_add(self._render_data, generation, loading, result)

        in_background(
            worker,
            lambda msg: self._render_data(generation, loading, UsageError(msg)),
        )

    def _on_refresh(self, _btn: Gtk.Button) -> None:
        self._build_content(force=True)

    def _render_data(
        self, generation: int, loading: Gtk.Label, result: Report | UsageError
    ) -> bool:
        """Main thread: replace the loading label with the fetched content."""
        if generation != self._generation:
            return GLib.SOURCE_REMOVE  # a newer rebuild already replaced this view
        self._container.remove(loading)
        match result:
            case UsageError() as e:
                self._show_error(str(e))
            case Report(windows=[]):
                self._show_error("no usage windows in response")
            case Report() as report:
                for window in report.windows:
                    self._build_window_row(self._container, window)
                self._build_spend_row(self._container, report.spend)
                self._build_charge_section(self._container, report)
        return GLib.SOURCE_REMOVE

    def _show_error(self, error: str) -> None:
        error_label = Gtk.Label(label=f"Failed to fetch usage data: {error}")
        error_label.add_css_class("usage-error")
        error_label.set_wrap(True)
        error_label.set_max_width_chars(40)
        copyable(error_label)
        self._container.append(error_label)

    def _build_window_row(self, container: Gtk.Box, window: Window) -> None:
        """Build a labeled progress bar row for one usage window."""
        pct = window.percent
        level = severity(pct)
        period = "5h" if window.kind == "session" else "7d"

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        name_label = Gtk.Label(label=window.label)
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

        if window.resets_at:
            reset_label = Gtk.Label(label=describe_reset(window.resets_at))
            reset_label.add_css_class("usage-reset")
            reset_label.set_halign(Gtk.Align.START)
            container.append(reset_label)

    def _build_spend_row(self, container: Gtk.Box, spend: Spend | None) -> None:
        """Show extra-usage spend when the account has it enabled."""
        if spend is None:
            return
        text = f"extra usage: {spend.amount:.2f} {spend.currency}"
        if spend.cap is not None:
            text += f" / {spend.cap:.2f} {spend.currency}"
        label = Gtk.Label(label=text)
        label.add_css_class("usage-charge-label")
        label.set_halign(Gtk.Align.START)
        container.append(label)

    def _build_charge_section(self, container: Gtk.Box, report: Report) -> None:
        """Show charge date if cached, or session key input if not."""
        separator = Gtk.Separator()
        separator.add_css_class("usage-separator")
        container.append(separator)

        charge_date = report.next_charge_date
        if charge_date:
            label = Gtk.Label(label=f"next charge: {describe_charge_date(charge_date)}")
            label.add_css_class("usage-charge-label")
            label.set_halign(Gtk.Align.START)
            container.append(label)
            return

        text = "paste session key to fetch billing info"
        if report.plan_changed:
            text = "plan changed: " + text
        hint = Gtk.Label(label=text)
        hint.add_css_class("session-label")
        hint.set_halign(Gtk.Align.START)
        container.append(hint)

        input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._session_entry = Gtk.Entry()
        self._session_entry.set_placeholder_text("sk-ant-sid02-...")
        self._session_entry.add_css_class("session-entry")
        self._session_entry.set_hexpand(True)
        self._session_entry.set_visibility(False)
        self._session_entry.connect("activate", self._on_submit)
        input_row.append(self._session_entry)

        self._submit_btn = Gtk.Button(label="save")
        self._submit_btn.add_css_class("session-button")
        self._submit_btn.connect("clicked", self._on_submit)
        input_row.append(self._submit_btn)

        container.append(input_row)

        self._status_label = Gtk.Label()
        self._status_label.set_halign(Gtk.Align.START)
        container.append(self._status_label)

    def _on_submit(self, _widget: Gtk.Widget) -> None:
        """Fetch subscription details off the main thread and cache the result."""
        session_key = self._session_entry.get_text().strip()
        if not session_key:
            return
        self._session_entry.set_sensitive(False)
        self._submit_btn.set_sensitive(False)
        self._set_session_status("fetching…", None)

        def worker() -> None:
            GLib.idle_add(self._on_submit_done, save_subscription(session_key))

        in_background(worker, lambda msg: self._on_submit_done(UsageError(msg)))

    def _on_submit_done(self, result: str | UsageError) -> bool:
        """result: the saved charge date."""
        self._session_entry.set_sensitive(True)
        self._submit_btn.set_sensitive(True)
        match result:
            case UsageError() as e:
                self._set_session_status(f"failed: {e}", "session-status-err")
            case charge_date:
                self._set_session_status(
                    f"saved — next charge: {describe_charge_date(charge_date)}",
                    "session-status-ok",
                )
                self._session_entry.set_text("")
        return GLib.SOURCE_REMOVE

    def _set_session_status(self, text: str, css_class: str | None) -> None:
        self._status_label.set_text(text)
        self._status_label.add_css_class("session-status")
        for cls in ("session-status-ok", "session-status-err"):
            self._status_label.remove_css_class(cls)
        if css_class:
            self._status_label.add_css_class(css_class)
        copyable(self._status_label, on=css_class == "session-status-err")


def main() -> int:
    return ClaudeUsagePopup().run()
