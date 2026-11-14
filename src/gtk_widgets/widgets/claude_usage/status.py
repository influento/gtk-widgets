#!/usr/bin/env python3
"""Fetch Claude subscription usage and output waybar-compatible JSON."""

import contextlib
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.lib.paths import module_child
from gtk_widgets.widgets.claude_usage import api
from gtk_widgets.widgets.claude_usage.parse import (
    ChargeCache,
    Usage,
    parse_charge_cache,
    parse_usage,
)
from gtk_widgets.widgets.claude_usage.usage import (
    UsageError,
    describe_charge_date,
    format_reset_absolute,
    format_reset_relative,
    reset_in_future,
    roll_charge_date,
    severity,
)

SUBSCRIPTION_CACHE = Path.home() / ".claude" / "subscription_cache.json"
USAGE_CACHE = Path.home() / ".claude" / "usage_cache.json"
CACHE_TTL = 600  # 10 minutes


def load_usage_cache() -> tuple[Usage | None, bool]:
    """Load cached usage data and freshness flag."""
    try:
        data: object = json.loads(USAGE_CACHE.read_text())
    except FileNotFoundError, ValueError:
        return None, False
    match parse_usage(data):
        case ParseError():
            return None, False
        case cache:
            return cache, time.time() - cache.cached_at < CACHE_TTL


def fetch_usage(token: str) -> Usage | UsageError:
    """Fetch usage data from the API and save it to the cache."""
    match api.get("/api/oauth/usage", api.oauth_headers(token), parse_usage):
        case UsageError() as e:
            return e
        case usage:
            pass
    try:
        USAGE_CACHE.write_text(json.dumps({**usage.raw, "_cached_at": time.time()}))
    except OSError as e:
        return UsageError(str(e))
    return usage


def load_charge_cache() -> ChargeCache:
    """subscription_cache.json; a missing, unreadable or malformed one is empty."""
    try:
        data: object = json.loads(SUBSCRIPTION_CACHE.read_text())
    except FileNotFoundError, ValueError:
        return ChargeCache()
    match parse_charge_cache(data):
        case ParseError():
            return ChargeCache()
        case cache:
            return cache


def load_cached_charge_date() -> str | None:
    """The next charge: the cached one, rolled forward a month at a time once it passes."""
    charge_date = load_charge_cache().next_charge_date
    return roll_charge_date(charge_date) if charge_date else None


def format_output(usage: Usage) -> dict[str, str]:
    """Format usage data as waybar JSON."""
    windows = usage.windows
    if not windows:
        return {"text": "no data", "tooltip": "", "class": "error"}
    css_class = severity(max((w.percent for w in windows), default=0))

    width = max(len(w.label) for w in windows) + 2
    tooltip_lines: list[str] = []
    for w in windows:
        pct = round(w.percent)
        line = f"{w.label + ':':<{width}}{pct:>3}%"
        if w.resets_at and reset_in_future(w.resets_at):
            line += f"  resets {format_reset_absolute(w.resets_at)} ({format_reset_relative(w.resets_at)})"
        tooltip_lines.append(line)

    charge_date = load_cached_charge_date()
    if charge_date:
        tooltip_lines.append(
            f"{'next charge:':<{width}}{describe_charge_date(charge_date)}"
        )

    parts: list[str] = []
    for w in windows:
        part = f"{w.short} - {round(w.percent)}%"
        if w.kind == "session" and w.resets_at and reset_in_future(w.resets_at):
            part += f" ({format_reset_relative(w.resets_at).replace(' ', ':')})"
        parts.append(part)

    return {
        "text": " · ".join(parts),
        "tooltip": "\n".join(tooltip_lines),
        "class": css_class,
    }


def print_json(usage: Usage) -> None:
    """Raw API data plus normalized windows and cached charge date, for the popup."""
    out = {k: v for k, v in usage.raw.items() if not k.startswith("_")}
    out["windows"] = [asdict(w) for w in usage.windows]
    charge_date = load_cached_charge_date()
    if charge_date:
        out["next_charge_date"] = charge_date
    print(json.dumps(out))


def refresh_cache() -> None:
    """Background-only: fetch fresh data and update cache, then exit."""
    token = api.load_token()
    if not isinstance(token, UsageError):
        _ = fetch_usage(token)


def main() -> None:
    if "--refresh-cache" in sys.argv:
        refresh_cache()
        return

    force = "--refresh" in sys.argv
    is_json = "--json" in sys.argv
    cached, fresh = load_usage_cache()

    # Fresh cache — render immediately, no API call
    if cached is not None and fresh and not force:
        if is_json:
            print_json(cached)
        else:
            print(json.dumps(format_output(cached)))
        return

    # Stale or no cache — print what we have and refresh in background (waybar)
    # or fetch synchronously (--json mode)
    if not is_json:
        if cached is not None:
            print(json.dumps(format_output(cached)))
        else:
            print(json.dumps({"text": "fetching…", "tooltip": "", "class": "error"}))
        # Refresh cache in background so waybar gets output immediately
        cmd, env = module_child(__spec__.name)  # __name__ is __main__ under -m
        with contextlib.suppress(OSError):
            subprocess.Popen(
                [*cmd, "--refresh-cache"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return

    # --json with a stale cache: fetch synchronously so the popup shows live data
    token = api.load_token()
    match token if isinstance(token, UsageError) else fetch_usage(token):
        case UsageError() as e:
            print(json.dumps({"error": str(e)}))
        case usage:
            print_json(usage)


if __name__ == "__main__":
    main()
