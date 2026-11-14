"""Claude's API answers, this widget's cache files and the status script's
--json output: their models and parsers.

Times and dates are checked here but kept as the text they came in, so
--json passes them on unchanged.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from gtk_widgets.lib.parse import (
    ParseError,
    as_array,
    as_bool,
    as_float,
    as_int,
    as_str,
    as_str_or_none,
    is_object,
)
from gtk_widgets.widgets.claude_usage.usage import UsageError

# Before the `limits` array: (key, kind, short, label)
LEGACY_WINDOWS = [
    ("five_hour", "session", "5h", "Current session"),
    ("seven_day", "weekly_all", "7d", "All models"),
]
DEFAULT_SPEND_EXPONENT = 2  # minor units per major: cents
_EMPTY: Mapping[str, object] = {}  # a missing or null object


@dataclass(frozen=True, slots=True)
class Window:
    """One usage window. The fields are in the order --json writes them."""

    kind: str | None
    short: str
    label: str
    percent: float
    resets_at: str | None  # ISO time
    severity: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class Usage:
    """The usage endpoint's answer, or the cache of it."""

    windows: list[Window]
    raw: Mapping[str, object]  # the whole answer, which --json passes on
    cached_at: float  # 0 when not from the cache


@dataclass(frozen=True, slots=True)
class Spend:
    """Extra usage, when the account has it on."""

    amount: float
    currency: str
    cap: float | None


@dataclass(frozen=True, slots=True)
class Report:
    """What the popup shows: the status script's --json output."""

    windows: list[Window]
    spend: Spend | None
    next_charge_date: str | None  # YYYY-MM-DD
    plan_changed: bool = False


@dataclass(frozen=True, slots=True)
class ChargeCache:
    """subscription_cache.json."""

    next_charge_date: str | None = None  # YYYY-MM-DD
    org_uuid: str | None = None
    plan: str | None = None  # None: saved before plans were recorded


@dataclass(frozen=True, slots=True)
class Org:
    """The OAuth profile's organization."""

    uuid: str
    plan: str  # what the billing day hangs on: a plan change can move it


def _opt_bool(value: object, path: str) -> bool | ParseError:
    return False if value is None else as_bool(value, path)


def _time(value: object, path: str) -> str | ParseError | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return ParseError(f"{path}: not a string")
    try:
        _ = datetime.fromisoformat(value)
    except ValueError:
        return ParseError(f"{path}: not an ISO time")
    return value


def _date(value: object, path: str) -> str | ParseError | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return ParseError(f"{path}: not a string")
    try:
        _ = date.fromisoformat(value)
    except ValueError:
        return ParseError(f"{path}: not a YYYY-MM-DD date")
    return value


def _display_name(value: object, path: str) -> str | ParseError | None:
    """A {display_name} object's name; None for a missing or empty object."""
    if not value:
        return None
    if not is_object(value):
        return ParseError(f"{path}: not an object")
    return as_str_or_none(value.get("display_name"), f"{path}.display_name")


def _labels(kind: str | None, name: str | None) -> tuple[str, str]:
    """(short, label) of a limit; name is its scope's model or surface."""
    if kind == "session":
        return "5h", "Current session"
    if kind == "weekly_all":
        return "7d", "All models"
    label = name or ("scoped" if kind == "weekly_scoped" else kind or "other")
    return label.lower(), label


def _limit(lim: object, path: str) -> Window | ParseError:
    if not is_object(lim):
        return ParseError(f"{path}: not an object")
    scope = lim.get("scope") or _EMPTY
    if not is_object(scope):
        return ParseError(f"{path}.scope: not an object")
    surface = scope.get("surface")
    match (
        as_str_or_none(lim.get("kind"), f"{path}.kind"),
        _display_name(scope.get("model"), f"{path}.scope.model"),
        _display_name(surface, f"{path}.scope.surface")
        if is_object(surface)
        else as_str_or_none(surface, f"{path}.scope.surface"),
        as_float(lim.get("percent") or 0, f"{path}.percent"),
        _time(lim.get("resets_at"), f"{path}.resets_at"),
        as_str_or_none(lim.get("severity"), f"{path}.severity"),
        _opt_bool(lim.get("is_active"), f"{path}.is_active"),
    ):
        case (
            (str() | None) as kind,
            (str() | None) as model,
            (str() | None) as surface_name,
            float() as percent,
            (str() | None) as resets_at,
            (str() | None) as severity,
            bool() as is_active,
        ):
            short, label = _labels(kind, model or surface_name)
            return Window(
                kind,
                short,
                label,
                percent,
                resets_at,
                severity or "normal",
                is_active,
            )
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))


def _legacy_windows(data: Mapping[str, object]) -> list[Window] | ParseError:
    windows: list[Window] = []
    for key, kind, short, label in LEGACY_WINDOWS:
        win = data.get(key)
        if not win:
            continue
        if not is_object(win):
            return ParseError(f".{key}: not an object")
        utilization = win.get("utilization")
        if utilization is None:
            continue
        match (
            as_float(utilization, f".{key}.utilization"),
            _time(win.get("resets_at"), f".{key}.resets_at"),
        ):
            case float() as percent, (str() | None) as resets_at:
                windows.append(
                    Window(
                        kind,
                        short,
                        label,
                        percent,
                        resets_at,
                        "normal",
                        is_active=False,
                    )
                )
            case fields:
                return next(f for f in fields if isinstance(f, ParseError))
    return windows


def parse_usage(data: object) -> Usage | ParseError:
    """The usage endpoint's answer, or its cache (the answer plus _cached_at).

    Windows come from the `limits` array (session / weekly_all /
    weekly_scoped), else from the legacy five_hour / seven_day objects.
    """
    if not is_object(data):
        return ParseError("not an object")
    cached_at = as_float(data.get("_cached_at", 0), "._cached_at")
    if isinstance(cached_at, ParseError):
        return cached_at
    limits = as_array(data.get("limits"), ".limits")
    if isinstance(limits, ParseError):
        return limits
    windows: list[Window] = []
    for i, lim in enumerate(limits):
        match _limit(lim, f".limits[{i}]"):
            case ParseError() as e:
                return e
            case window:
                windows.append(window)
    if not windows:
        match _legacy_windows(data):
            case ParseError() as e:
                return e
            case legacy:
                windows = legacy
    return Usage(windows, data, cached_at)


def _window(value: object, path: str) -> Window | ParseError:
    """One window as --json writes it."""
    if not is_object(value):
        return ParseError(f"{path}: not an object")
    match (
        as_str_or_none(value.get("kind"), f"{path}.kind"),
        as_str(value.get("short"), f"{path}.short"),
        as_str(value.get("label"), f"{path}.label"),
        as_float(value.get("percent"), f"{path}.percent"),
        _time(value.get("resets_at"), f"{path}.resets_at"),
        as_str(value.get("severity"), f"{path}.severity"),
        as_bool(value.get("is_active"), f"{path}.is_active"),
    ):
        case (
            (str() | None) as kind,
            str() as short,
            str() as label,
            float() as percent,
            (str() | None) as resets_at,
            str() as severity,
            bool() as is_active,
        ):
            return Window(kind, short, label, percent, resets_at, severity, is_active)
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))


def _spend(value: object) -> Spend | ParseError | None:
    """None when extra usage is off."""
    if not value:
        return None
    if not is_object(value):
        return ParseError(".spend: not an object")
    enabled = _opt_bool(value.get("enabled"), ".spend.enabled")
    if enabled is not True:
        return enabled or None
    used = value.get("used") or _EMPTY
    if not is_object(used):
        return ParseError(".spend.used: not an object")
    match (
        as_int(used.get("exponent", DEFAULT_SPEND_EXPONENT), ".spend.used.exponent"),
        as_float(used.get("amount_minor", 0), ".spend.used.amount_minor"),
        as_str(used.get("currency", "USD"), ".spend.used.currency"),
    ):
        case int() as exponent, float() as minor, str() as currency:
            pass
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))
    limit = value.get("limit")
    cap = None
    if is_object(limit) and limit.get("amount_minor") is not None:
        match (
            as_float(limit.get("amount_minor"), ".spend.limit.amount_minor"),
            as_int(limit.get("exponent", exponent), ".spend.limit.exponent"),
        ):
            case float() as cap_minor, int() as cap_exponent:
                cap = cap_minor / (10**cap_exponent)
            case fields:
                return next(f for f in fields if isinstance(f, ParseError))
    return Spend(minor / (10**exponent), currency, cap)


def parse_report(data: object) -> Report | UsageError | ParseError:
    """The status script's --json output; its {"error": ...} is a UsageError."""
    if not is_object(data):
        return ParseError("not an object")
    if "error" in data:
        return UsageError(str(data["error"]))
    windows_data = as_array(data.get("windows"), ".windows")
    if isinstance(windows_data, ParseError):
        return windows_data
    windows: list[Window] = []
    for i, value in enumerate(windows_data):
        match _window(value, f".windows[{i}]"):
            case ParseError() as e:
                return e
            case window:
                windows.append(window)
    match (
        _spend(data.get("spend")),
        _date(data.get("next_charge_date") or None, ".next_charge_date"),
    ):
        case (Spend() | None) as spend, (str() | None) as charge_date:
            return Report(windows, spend, charge_date)
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))


def parse_charge_cache(data: object) -> ChargeCache | ParseError:
    if not is_object(data):
        return ParseError("not an object")
    match (
        _date(data.get("next_charge_date") or None, ".next_charge_date"),
        as_str_or_none(data.get("org_uuid"), ".org_uuid"),
        as_str_or_none(data.get("plan"), ".plan"),
    ):
        case (str() | None) as charge_date, (str() | None) as uuid, (
            str() | None
        ) as plan:
            return ChargeCache(charge_date, uuid, plan)
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))


def parse_token(data: object) -> str | ParseError:
    """Claude Code's credentials file: the OAuth access token."""
    oauth = data.get("claudeAiOauth") if is_object(data) else None
    if not is_object(oauth):
        return ParseError(".claudeAiOauth: not an object")
    return as_str(oauth.get("accessToken"), ".claudeAiOauth.accessToken")


def parse_profile(data: object) -> Org | ParseError:
    """The OAuth profile endpoint's answer: its organization."""
    org = data.get("organization") if is_object(data) else None
    if not is_object(org):
        return ParseError(".organization: not an object")
    plan = "/".join(
        str(org.get(k))
        for k in ("organization_type", "rate_limit_tier", "subscription_status")
    )
    match as_str(org.get("uuid"), ".organization.uuid"):
        case ParseError() as e:
            return e
        case uuid:
            return Org(uuid, plan)


def parse_charge_date(data: object) -> str | ParseError:
    """The subscription details endpoint's answer: its next charge date."""
    found = data.get("next_charge_date") if is_object(data) else None
    match _date(found or None, ".next_charge_date"):
        case None:
            return ParseError("no next_charge_date in response")
        case charge_date:
            return charge_date
