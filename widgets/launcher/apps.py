"""Desktop entries for drun mode: listing, usage ranking, launching."""

import json
import os
import tempfile
import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from match import Field  # noqa: E402

TERMINAL = ["ghostty", "-e"]  # Terminal=true entries run inside this
HALF_LIFE_S = 14 * 86400      # a launch counts half as much after two weeks
_PRELOAD = "libgtk4-layer-shell.so.0"
# Exec field codes that expand to nothing here: no files or URLs are passed
_DROPPED_CODES = set("fFuUdDnNvm")


def usage_path():
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(cache, "launcher", "usage.json")


class Usage:
    """Launch counts with exponential recency decay: each launch adds 1 and
    the total halves every HALF_LIFE_S. Stored as {id: {score, time}}, the
    score valid at time."""

    def __init__(self, path=None):
        self.path = path or usage_path()
        self.data = {}
        try:
            with open(self.path) as f:
                data = json.load(f)
            self.data = {k: v for k, v in data.items()
                         if isinstance(v, dict) and isinstance(v.get("score"), (int, float))
                         and isinstance(v.get("time"), (int, float))}
        except (OSError, ValueError, AttributeError):
            pass

    def score(self, key, now=None):
        entry = self.data.get(key)
        if entry is None:
            return 0.0
        now = time.time() if now is None else now
        return entry["score"] * 0.5 ** (max(0.0, now - entry["time"]) / HALF_LIFE_S)

    def bump(self, key):
        now = time.time()
        self.data[key] = {"score": self.score(key, now) + 1.0, "time": now}
        self.save()

    def save(self):
        """Write atomically: a temp file in the same directory, then rename."""
        folder = os.path.dirname(self.path)
        try:
            os.makedirs(folder, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=folder, prefix=".usage-")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self.data, f, indent=0, sort_keys=True)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.path)
            except BaseException:
                os.unlink(tmp)
                raise
        except OSError as e:
            print(f"launcher: can't save usage: {e}", flush=True)


class App:
    """One desktop entry, with its search fields prepared."""

    __slots__ = ("info", "id", "name", "icon", "detail", "field", "extra", "sort")

    def __init__(self, info):
        self.info = info
        self.id = info.get_id() or info.get_filename() or info.get_name()
        self.name = info.get_display_name() or info.get_name() or self.id
        self.icon = info.get_icon()
        self.detail = ""
        self.field = Field(self.name)
        extra = [info.get_generic_name(), *(info.get_keywords() or [])]
        exe = info.get_executable()
        if exe:
            extra.append(os.path.basename(exe))
        self.extra = tuple(Field(x) for x in extra if x)
        self.sort = (self.name.casefold(), self.id)


def load_apps():
    """Every entry the desktop should list (should_show: NoDisplay, Hidden,
    OnlyShowIn/NotShowIn). Entries that share a name get their desktop id as
    a dim detail so they can be told apart."""
    apps = [App(info) for info in Gio.AppInfo.get_all() if info.should_show()]
    names = {}
    for app in apps:
        names.setdefault(app.sort[0], []).append(app)
    for same in names.values():
        if len(same) > 1:
            for app in same:
                app.detail = app.id.removesuffix(".desktop")
    return apps


def child_environment():
    """Remove the layer-shell preload from this process's environment, which
    launched apps inherit: it is loaded already, and it must not end up in
    every app started from here."""
    kept = [p for p in os.environ.get("LD_PRELOAD", "").replace(" ", ":").split(":")
            if p and os.path.basename(p) != _PRELOAD]
    if kept:
        os.environ["LD_PRELOAD"] = ":".join(kept)
    else:
        os.environ.pop("LD_PRELOAD", None)


def _expand(arg, info):
    """Expand the field codes inside one Exec argument (no files are passed)."""
    out, i = [], 0
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


def exec_argv(info):
    """The entry's Exec as argv with its field codes expanded or dropped."""
    ok, argv = GLib.shell_parse_argv(info.get_string("Exec") or "")
    out = []
    for arg in argv if ok else []:
        if len(arg) == 2 and arg[0] == "%" and arg[1] in _DROPPED_CODES:
            continue
        if arg == "%i":
            icon = info.get_string("Icon")
            if icon:
                out += ["--icon", icon]
            continue
        out.append(_expand(arg, info))
    return out


def launch(info, context):
    """Start the entry; Terminal=true entries run as `ghostty -e <cmd>`. The
    spawn is detached (GLib double-forks), so apps outlive the launcher.
    Returns an error message, or None."""
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
            info = Gio.AppInfo.create_from_commandline(
                cmd, info.get_name(), Gio.AppInfoCreateFlags.NONE)
        info.launch([], context)
    except GLib.Error as e:
        return e.message
    return None


def notify_error(summary, body):
    try:
        GLib.spawn_async(["notify-send", "-a", "Launcher", "-u", "critical",
                          "-i", "dialog-error", summary, body],
                         flags=GLib.SpawnFlags.SEARCH_PATH
                         | GLib.SpawnFlags.STDOUT_TO_DEV_NULL
                         | GLib.SpawnFlags.STDERR_TO_DEV_NULL)
    except GLib.Error as e:
        print(f"launcher: {summary}: {body} (notify-send: {e.message})", flush=True)
