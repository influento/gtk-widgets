"""Formatting shared by the claude-usage popup and its status script."""

from datetime import datetime, timezone


def _parse_iso(iso_str):
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


def format_reset_relative(iso_str):
    """Reset time as a relative duration: '1d 2h', '2h 5m', '5m', or 'now'."""
    delta = _parse_iso(iso_str) - datetime.now(timezone.utc)
    total_minutes = int(delta.total_seconds() / 60)
    if total_minutes < 0:
        return "now"
    total_hours, minutes = divmod(total_minutes, 60)
    if total_hours >= 24:
        days, hours = divmod(total_hours, 24)
        return f"{days}d {hours}h"
    if total_hours > 0:
        return f"{total_hours}h {minutes}m"
    return f"{minutes}m"


def format_reset_absolute(iso_str):
    """Reset time as a local day and time (e.g., 'Fri 10:59 AM')."""
    return _parse_iso(iso_str).astimezone().strftime("%a %-I:%M %p")


def reset_in_future(iso_str):
    """True if a reset timestamp is present and still ahead of now."""
    return bool(iso_str) and _parse_iso(iso_str) > datetime.now(timezone.utc)


def describe_reset(iso_str):
    """'resets Fri 10:59 AM (2h 5m)', or 'resets now' once the window has passed."""
    relative = format_reset_relative(iso_str)
    if relative == "now":
        return "resets now"
    return f"resets {format_reset_absolute(iso_str)} ({relative})"


def format_date_relative(date_str):
    """A YYYY-MM-DD date (taken as UTC midnight) as a relative duration."""
    target = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    delta = target - datetime.now(timezone.utc)
    total_hours = int(delta.total_seconds() / 3600)
    if total_hours < 0:
        return "now"
    if total_hours >= 24:
        days, hours = divmod(total_hours, 24)
        return f"{days}d {hours}h"
    minutes = int((delta.total_seconds() % 3600) / 60)
    return f"{total_hours}h {minutes}m"


def format_date_absolute(date_str):
    """A YYYY-MM-DD date as a short readable date (e.g., 'Apr 3')."""
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %-d")


def describe_charge_date(date_str):
    """'Oct 7 (19d 22h)'."""
    return f"{format_date_absolute(date_str)} ({format_date_relative(date_str)})"


def severity(pct):
    """CSS class for a utilization percentage: low / medium / high."""
    if pct > 95:
        return "high"
    if pct >= 80:
        return "medium"
    return "low"
