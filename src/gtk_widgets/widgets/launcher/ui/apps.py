"""Desktop entries for drun mode: listing, usage ranking, launching."""

import json
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from gi.repository import Gio, GLib

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.widgets.launcher.match import Field
from gtk_widgets.widgets.launcher.parse import Launches, parse_usage

TERMINAL = ["ghostty", "-e"]  # Terminal=true entries run inside this
HALF_LIFE_S = 14 * 86400  # a launch counts half as much after two weeks
_PRELOAD = "libgtk4-layer-shell.so.0"
# Exec field codes that expand to nothing here: no files or URLs are passed
_DROPPED_CODES = set("fFuUdDnNvm")
FIELD_CODE_LEN = 2  # "%" and a letter


def usage_path() -> Path:
    cache = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(cache) / "launcher" / "usage.json"


class Usage:
    """Launch counts with exponential recency decay: each launch adds 1 and
    the total halves every HALF_LIFE_S. Stored as {id: {score, time}}, the
    score valid at time."""

    def __init__(self) -> None:
        self.path = usage_path()
        self.data: dict[str, Launches] = {}
        try:
            data: object = json.loads(self.path.read_text())
        except OSError, ValueError:
            return
        match parse_usage(data):
            case ParseError():
                pass
            case usage:
                self.data = usage

    def score(self, key: str, now: float | None = None) -> float:
        entry = self.data.get(key)
        if entry is None:
            return 0.0
        now = time.time() if now is None else now
        return entry.score * 0.5 ** (max(0.0, now - entry.time) / HALF_LIFE_S)

    def bump(self, key: str) -> None:
        now = time.time()
        self.data[key] = Launches(self.score(key, now) + 1.0, now)
        self.save()

    def save(self) -> None:
        """Write atomically: a temp file in the same directory, then rename."""
        folder = self.path.parent
        try:
            folder.mkdir(exist_ok=True, parents=True)
            fd, tmp = tempfile.mkstemp(dir=folder, prefix=".usage-")
            try:
                with os.fdopen(fd, "w") as f:
                    data = {key: asdict(entry) for key, entry in self.data.items()}
                    json.dump(data, f, indent=0, sort_keys=True)
                    f.flush()
                    os.fsync(f.fileno())
                Path(tmp).replace(self.path)
            except BaseException:
                Path(tmp).unlink()
                raise
        except OSError as e:
            print(f"launcher: can't save usage: {e}", flush=True)


class App:
    """One desktop entry, with its search fields prepared."""

    __slots__ = ("detail", "extra", "field", "icon", "id", "info", "name", "sort")

    def __init__(self, info: Gio.DesktopAppInfo) -> None:
        self.info = info
        self.id: str = info.get_id() or info.get_filename() or info.get_name()
        self.name: str = info.get_display_name() or info.get_name() or self.id
        self.icon = info.get_icon()
        self.detail = ""
        self.field = Field(self.name)
        extra = [info.get_generic_name(), *(info.get_keywords() or [])]
        exe = info.get_executable()
        if exe:
            extra.append(exe.rpartition("/")[2])
        self.extra = tuple(Field(x) for x in extra if x)
        self.sort = (self.name.casefold(), self.id)


def load_apps() -> list[App]:
    """Every entry the desktop should list (should_show: NoDisplay, Hidden,
    OnlyShowIn/NotShowIn). Entries that share a name get their desktop id as
    a dim detail so they can be told apart."""
    apps = [
        App(info)
        for info in Gio.AppInfo.get_all()
        if isinstance(info, Gio.DesktopAppInfo) and info.should_show()
    ]
    names: dict[str, list[App]] = {}
    for app in apps:
        names.setdefault(app.sort[0], []).append(app)
    for same in names.values():
        if len(same) > 1:
            for app in same:
                app.detail = app.id.removesuffix(".desktop")
    return apps


def child_environment() -> None:
    """Remove the layer-shell preload from this process's environment, which
    launched apps inherit: it is loaded already, and it must not end up in
    every app started from here."""
    kept = [
        p
        for p in os.environ.get("LD_PRELOAD", "").replace(" ", ":").split(":")
        if p and p.rpartition("/")[2] != _PRELOAD
    ]
    if kept:
        os.environ["LD_PRELOAD"] = ":".join(kept)
    else:
        os.environ.pop("LD_PRELOAD", None)


def _expand(arg: str, info: Gio.DesktopAppInfo) -> str:
    """Expand the field codes inside one Exec argument (no files are passed)."""
    out: list[str] = []
    i = 0
    while i < len(arg):
        ch = arg[i]
        if ch == "%" and i + 1 < len(arg):
            code = arg[i + 1]
            if code == "%":
                out.append("%")
            elif code == "c":
                out.append(info.get_name() or "")
            elif code == "k":
                out.append(info.get_filename() or "")
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def exec_argv(info: Gio.DesktopAppInfo) -> list[str]:
    """The entry's Exec as argv with its field codes expanded or dropped."""
    ok, argv = GLib.shell_parse_argv(info.get_string("Exec") or "")
    out: list[str] = []
    for arg in argv if ok else []:
        if len(arg) == FIELD_CODE_LEN and arg[0] == "%" and arg[1] in _DROPPED_CODES:
            continue
        if arg == "%i":
            icon = info.get_string("Icon")
            if icon:
                out += ["--icon", icon]
            continue
        out.append(_expand(arg, info))
    return out


def launch(info: Gio.DesktopAppInfo, context: Gio.AppLaunchContext) -> str | None:
    """Start the entry; Terminal=true entries run as `ghostty -e <cmd>`. The
    spawn is detached (GLib double-forks), so apps outlive the launcher.
    Returns an error message, or None."""
    target: Gio.AppInfo = info
    try:
        if info.get_boolean("Terminal"):
            argv = exec_argv(info)
            if not argv:
                return "Exec is empty"
            term = list(TERMINAL)
            path = info.get_string("Path")
            if path:
                term.insert(1, f"--working-directory={path}")
            # create_from_commandline treats % as a field code and appends %f
            cmd = " ".join(GLib.shell_quote(a) for a in term + argv).replace("%", "%%")
            target = Gio.AppInfo.create_from_commandline(
                cmd, info.get_name(), Gio.AppInfoCreateFlags.NONE
            )
        target.launch([], context)
    except GLib.Error as e:
        return e.message
    return None


def notify_error(summary: str, body: str) -> None:
    try:
        Gio.Subprocess.new(
            [
                "notify-send",
                "-a",
                "Launcher",
                "-u",
                "critical",
                "-i",
                "dialog-error",
                summary,
                body,
            ],
            Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE,
        )
    except GLib.Error as e:
        print(f"launcher: {summary}: {body} (notify-send: {e.message})", flush=True)
