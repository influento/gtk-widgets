#!/usr/bin/env python3
"""capture — screenshots and screen clips at the output's own pixels.

  capture region [--dir DIR] [--copy]
        freeze every output, drag a rectangle (or click a window, or the
        bar or wallpaper for the whole output), save it as
        DIR/screenshot-%Y%m%d-%H%M%S.png and print the file's absolute path;
        --copy also puts file://<path> on the clipboard (text/uri-list).
        Exit 0 on save; 1 when cancelled (Esc, right click) or when another
        capture is open, with no file; 2 on errors.
        DIR defaults to $XDG_PICTURES_DIR/screenshots.

  capture gif [--dir DIR] [--copy]
        pick a region, window or output the same way, record it (30 fps, 60 s at most) until
        `capture gif` runs again, then write DIR/recording-%Y%m%d-%H%M%S/
        with recording.gif (every frame), then sheet.png (the frames that
        show something new, tiled and labelled, for an AI; sheet-1.png,
        sheet-2.png, ... when they need several) and frames/ (those frames at
        full size), print the folder's path and send a notification. --copy
        puts file://<path> of the GIF on the clipboard (text/uri-list) as
        soon as it is written, then of the sheets (one list), so the sheets
        are on top and the GIF is next in the history. Exit codes as for
        region. DIR defaults to $XDG_PICTURES_DIR/recordings.
  capture gif --cancel
        stop a recording and throw it away (exit 1 with none going).

The frames are grabbed with wlr-screencopy (screencopy.py, stdlib) before GTK
is even imported, so nothing of ours is on screen yet and nothing has lost
focus: that raw buffer, at physical resolution, is the frozen frame, and the
saved PNG is cut from it without any scaling. $CAPTURE_T0 (ns since the
epoch) prints how long after it the frozen frame was painted.
"""

import contextlib
import ctypes
import fcntl
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Literal, NamedTuple, NoReturn

from gtk_widgets.lib.paths import SRC
from gtk_widgets.widgets.capture import process, record, screencopy, swayipc
from gtk_widgets.widgets.capture.geometry import Rect
from gtk_widgets.widgets.capture.parse import Output

USAGE = "usage: capture region [--dir DIR] [--copy]\n       capture gif [--dir DIR] [--copy] | --cancel"
EXIT_CANCELLED = 1  # also: another capture is open
EXIT_ERROR = 2
_PRELOAD = "libgtk4-layer-shell.so.0"
_PID_FILE = "gtk-widgets-capture-gif.pid"
_LOCK_FILE = "gtk-widgets-capture.lock"
_WL_COPY_TIMEOUT_S = 5
_CLIPHIST_TIMEOUT_S = 2
_CLIPHIST_WAIT_S = 2  # for cliphist to store the GIF before the sheets
_CLIPHIST_POLL_S = 0.05
_LOG_LINES = 5  # of wf-recorder's log, when it stopped by itself
_GIF_TOOLS = ("wf-recorder", "ffmpeg", "ffprobe")

type Mode = Literal["region", "gif"]


class Args(NamedTuple):
    mode: Mode
    directory: str | None
    copy: bool
    cancel: bool


def usage() -> NoReturn:
    print(USAGE, file=sys.stderr)
    sys.exit(EXIT_ERROR)


def parse_args(argv: list[str]) -> Args:
    args = list(argv)
    if args and args[0] in {"-h", "--help"}:
        print((__doc__ or "").strip())
        sys.exit(0)
    mode: Mode
    match args.pop(0) if args else None:
        case "region" | "gif" as given:
            mode = given
        case _:
            usage()
    directory, copy, cancel = None, False, False
    while args:
        arg = args.pop(0)
        if arg == "--dir" and args:
            directory = args.pop(0)
        elif arg.startswith("--dir="):
            directory = arg.split("=", 1)[1]
        elif arg == "--copy":
            copy = True
        elif arg == "--cancel" and mode == "gif":
            cancel = True
        else:
            usage()
    if directory == "" or (cancel and (directory is not None or copy)):
        usage()
    return Args(mode, directory, copy, cancel)


def _expand(path: str) -> str:
    """path with ~ expanded, or as it is when there is no home to expand it
    to (os.path.expanduser; Path.expanduser raises)."""
    try:
        return str(Path(path).expanduser())
    except RuntimeError:
        return path


def pictures_dir() -> Path:
    """$XDG_PICTURES_DIR, from the environment or user-dirs.dirs, else ~/Pictures."""
    home = _expand("~")
    value = os.environ.get("XDG_PICTURES_DIR")
    if not value:
        config = os.environ.get("XDG_CONFIG_HOME") or str(Path(home, ".config"))
        try:
            with Path(config, "user-dirs.dirs").open() as f:
                for line in f:
                    key, _, raw = line.strip().partition("=")
                    if key == "XDG_PICTURES_DIR":
                        value = raw.strip('"').replace("$HOME", home)
        except OSError:
            pass
    if not value or not Path(value).is_absolute():
        return Path(home, "Pictures")
    return Path(value)


def runtime_dir() -> Path:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    return runtime if runtime.is_dir() else Path(tempfile.gettempdir())


def take_lock() -> int | None:
    """An open fd holding the lock, or None when another capture holds it."""
    fd = os.open(
        runtime_dir() / _LOCK_FILE, os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC, 0o600
    )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


@contextlib.contextmanager
def load_gtk() -> Generator[None]:
    """Import the GTK side inside it. gtk4-layer-shell has to be loaded
    before libwayland-client: loading it here, global, is what LD_PRELOAD
    does, without starting the process over (the frames are in memory)."""
    ctypes.CDLL(_PRELOAD, mode=ctypes.RTLD_GLOBAL)
    before = os.environ.get("LD_PRELOAD")
    os.environ["LD_PRELOAD"] = _PRELOAD  # lib/ui re-executes without it
    try:
        yield
    finally:
        if before is None:
            del os.environ["LD_PRELOAD"]
        else:
            os.environ["LD_PRELOAD"] = before


def free_path(
    directory: Path, stamp: str, prefix: str = "screenshot", suffix: str = ".png"
) -> Path:
    base = f"{prefix}-{stamp}"
    path, n = directory / f"{base}{suffix}", 1
    while path.exists(follow_symlinks=False):
        n += 1
        path = directory / f"{base}-{n}{suffix}"
    return path


def copy_uri(*paths: Path) -> bool:
    # wl-copy stays behind to serve the clipboard: keep it off our stdout, or
    # a caller reading it ($(capture region)) would wait for it to exit
    try:
        subprocess.run(
            ["wl-copy", "-t", "text/uri-list", "\r\n".join(p.as_uri() for p in paths)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=_WL_COPY_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError) as e:
        print(f"capture: copying to the clipboard failed: {e}", file=sys.stderr)
        return False
    return True


def copy_gif(gif: Path) -> bytes | None:
    """file://<path> of the GIF (text/uri-list, as for region), as soon as it
    is written. Returns what copy_sheets() needs: cliphist's newest entry
    from before (None without cliphist or when the copy failed)."""
    before = _cliphist_top()
    return before if copy_uri(gif) else None


def copy_sheets(sheets: list[Path], before: bytes | None) -> None:
    """file://<path> of the sheets in one list, so they are the newest
    clipboard item and the GIF the one below it. The history (cliphist) only
    keeps the GIF if it has stored it before the sheets replace it
    (`wl-paste --watch` skips an item replaced before it read it): it has
    had the whole processing time, and gets _CLIPHIST_WAIT_S more at most."""
    if before is not None:
        deadline = time.monotonic() + _CLIPHIST_WAIT_S
        while _cliphist_top() == before and time.monotonic() < deadline:
            time.sleep(_CLIPHIST_POLL_S)
    copy_uri(*sheets)


def _cliphist_top() -> bytes | None:
    """cliphist's newest entry, b"" for none, None without cliphist."""
    try:
        r = subprocess.run(
            ["cliphist", "list"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=_CLIPHIST_TIMEOUT_S,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None
    return r.stdout.split(b"\n", 1)[0]


def pid_path() -> Path:
    return runtime_dir() / _PID_FILE


def write_pid() -> None:
    path = pid_path()
    tmp = path.with_name(f"{_PID_FILE}.new")
    tmp.write_text(f"{os.getpid()}\n")
    tmp.replace(path)


def remove_pid() -> None:
    path = pid_path()
    try:
        if path.read_text().strip() == str(os.getpid()):
            path.unlink()
    except OSError, ValueError:
        pass


def signal_recorder(*, cancel: bool) -> int:
    """The lock is taken: when a recording holds it, stop it (SIGUSR1) or
    throw it away (SIGUSR2, --cancel) and exit 0 quietly; else another
    capture is open."""
    try:
        pid = int(pid_path().read_text().strip())
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        # a pid file left by a killed recording may name another process now
        if b"gif" in argv and any(
            a.rpartition(b"/")[2] in {b"capture", b"main.py"} for a in argv
        ):
            os.kill(pid, signal.SIGUSR2 if cancel else signal.SIGUSR1)
            return 0
    except OSError, ValueError:
        pass
    if not cancel:
        print("capture: another capture is open", file=sys.stderr)
    return EXIT_CANCELLED


def fail(message: str | BaseException) -> int:
    print(f"capture: {message}", file=sys.stderr)
    return EXIT_ERROR


def notify(summary: str, body: str, urgency: str = "normal") -> None:
    with contextlib.suppress(OSError):
        subprocess.Popen(
            ["notify-send", "-a", "capture", "-u", urgency, summary, body],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _target_dir(directory: str | None, default: str) -> Path:
    return process.absolute(_expand(directory or str(pictures_dir() / default)))


def main_region(*, directory: str | None, copy: bool) -> int:
    given_t0 = os.environ.pop("CAPTURE_T0", None)
    lock = take_lock()
    if lock is None:
        print("capture: another capture is open", file=sys.stderr)
        return EXIT_CANCELLED
    stamp = time.strftime("%Y%m%d-%H%M%S")
    try:
        frames = screencopy.capture_outputs()
    except (screencopy.CaptureError, OSError) as e:
        return fail(e)
    scales = swayipc.output_scales()
    windows = swayipc.windows()  # as the frames show them
    t0 = int(given_t0) if given_t0 else None
    if t0 is not None:
        print(
            f"capture: {len(frames)} output(s) grabbed {(time.time_ns() - t0) / 1e6:.1f} ms"
            " after launch",
            file=sys.stderr,
            flush=True,
        )

    with load_gtk():
        from gtk_widgets.widgets.capture.ui import app, image
    result = app.pick_region(frames, scales, t0, windows)
    if result is None:
        return EXIT_CANCELLED
    picture, rect = result

    folder = _target_dir(directory, "screenshots")
    try:
        folder.mkdir(exist_ok=True, parents=True)
        path = free_path(folder, stamp)
        image.save_png(picture.crop(*rect), str(path))
    except (OSError, ValueError) as e:
        return fail(e)
    print(path, flush=True)
    if copy:
        copy_uri(path)
    return 0


def main_gif(*, directory: str | None, copy: bool, cancel: bool) -> int:
    lock = take_lock()
    if lock is None:
        return signal_recorder(cancel=cancel)
    if cancel:
        return EXIT_CANCELLED  # no recording going
    missing = [tool for tool in _GIF_TOOLS if not shutil.which(tool)]
    if missing:
        return fail(f"gif needs {', '.join(missing)}")
    return _gif(directory=directory, copy=copy)


def _gif(*, directory: str | None, copy: bool) -> int:
    try:
        frames = screencopy.capture_outputs()
    except (screencopy.CaptureError, OSError) as e:
        return fail(e)
    outputs = swayipc.outputs()
    windows = swayipc.windows()

    with load_gtk():
        from gtk_widgets.widgets.capture.ui import app
    result = app.pick_region(
        frames, {name: o.scale for name, o in outputs.items()}, windows=windows
    )
    if result is None:
        return EXIT_CANCELLED
    picture, rect = result
    name = picture.output.name
    target = _gif_target(name, rect, frames, outputs)
    if isinstance(target, str):
        return fail(target)
    out, plan = target

    # The first frame must not show the picker: the compositor has handled
    # its unmap after the roundtrip, and a screencopy returns only once it
    # has rendered a frame since
    app.wait_unmapped()
    try:
        screencopy.capture_outputs()
        folder_in = _target_dir(directory, "recordings")
        folder_in.mkdir(exist_ok=True, parents=True)
        folder = free_path(folder_in, time.strftime("%Y%m%d-%H%M%S"), "recording", "")
        folder.mkdir()
    except (screencopy.CaptureError, OSError) as e:
        return fail(e)

    def run(recorder: record.Recorder) -> str | None:
        return app.record(
            name,
            plan.rect,
            out.scale,
            recorder,
            max_seconds=record.MAX_SECONDS,
            on_started=write_pid,
            on_stopped=remove_pid,
        )

    rec = record.Recorder(
        record.command(
            name, (out.rect[0], out.rect[1]), plan, str(folder / process.RAW)
        )
    )
    return _record_gif(rec, run, folder, out.scale, copy=copy)


def _gif_target(
    name: str, rect: Rect, frames: list[screencopy.Frame], outputs: dict[str, Output]
) -> tuple[Output, record.Plan] | str:
    """The output a gif's rect is on and the plan to record it, or why it
    can't be recorded."""
    out = outputs.get(name)
    if out is None:
        return f"gif needs sway's output layout for {name!r} (is $SWAYSOCK set?)"
    if out.transform != "normal" or any(
        f.y_invert for f in frames if f.output.name == name
    ):
        return "gif can't record a rotated or flipped output"
    try:
        plan = record.plan(rect, out.scale, (out.rect[2], out.rect[3]))
    except ValueError as e:
        return str(e)
    if plan.rect != rect:
        print(
            f"capture: the output's far edge can't be recorded at scale {out.scale}:"
            f" recording {plan.rect[2]}x{plan.rect[3]} of {rect[2]}x{rect[3]}",
            file=sys.stderr,
        )
    return out, plan


def _record_gif(
    rec: record.Recorder,
    run: Callable[[record.Recorder], str | None],
    folder: Path,
    scale: float,
    *,
    copy: bool,
) -> int:
    try:
        rec.start()
        outcome = run(rec)
    except BaseException as e:
        remove_pid()
        if rec.proc is not None:
            rec.stop()
        shutil.rmtree(folder, ignore_errors=True)
        if isinstance(e, OSError):
            return fail(f"cannot start wf-recorder: {e}")
        raise
    remove_pid()

    if outcome == "cancelled":
        shutil.rmtree(folder, ignore_errors=True)
        return EXIT_CANCELLED
    if outcome != "stopped":
        shutil.rmtree(folder, ignore_errors=True)
        log = rec.output().strip().splitlines()[-_LOG_LINES:]
        return fail("wf-recorder stopped by itself: " + " / ".join(log))
    return _process_gif(rec, folder, scale, copy=copy)


def _process_gif(
    rec: record.Recorder, folder: Path, scale: float, *, copy: bool
) -> int:
    """The GIF first, on the clipboard as soon as it is written; then the sheets."""
    retry = f"PYTHONPATH={SRC} python3 -m {process.__name__} {folder} {scale}"
    try:
        _check_region(rec)
        gif = process.make_gif(str(folder))
        before = copy_gif(Path(gif)) if copy else None
        result = process.make_sheets(str(folder), scale)
    except (process.ProcessError, OSError) as e:
        notify("Recording failed", str(e), "critical")
        fail(e)
        return fail(f"the recording is kept in {folder}; retry with {retry}")
    print(folder, flush=True)
    frames, sheets = len(result.frames), len(result.sheets)
    summary = (
        f"{frames} frame{'s' * (frames != 1)} on {sheets} sheet{'s' * (sheets != 1)}"
    )
    if copy:
        copy_sheets([Path(s) for s in result.sheets], before)
        notify("Recording ready", f"{summary}, copied")
    else:
        notify("Recording ready", f"{summary} in {folder}")
    return 0


def _check_region(rec: record.Recorder) -> None:
    """Raise ProcessError when wf-recorder found the region invalid (it then
    records the whole output)."""
    error = rec.region_error()
    if error:
        raise process.ProcessError(error)


def _main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.mode == "gif":
        return main_gif(directory=args.directory, copy=args.copy, cancel=args.cancel)
    return main_region(directory=args.directory, copy=args.copy)


def main() -> int | None:
    try:
        return _main(sys.argv[1:])
    except KeyboardInterrupt:
        return EXIT_CANCELLED
