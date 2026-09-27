#!/usr/bin/env python3
"""capture — screenshots and screen clips at the output's own pixels.

  capture region [--dir DIR] [--copy]
        freeze every output, drag a rectangle, save it as
        DIR/screenshot-%Y%m%d-%H%M%S.png and print the file's absolute path;
        --copy also puts file://<path> on the clipboard (text/uri-list).
        Exit 0 on save; 1 when cancelled (Esc, right click) or when another
        capture is open, with no file; 2 on errors.
        DIR defaults to $XDG_PICTURES_DIR/screenshots.

  capture gif [--dir DIR] [--copy]
        pick a region the same way, record it (30 fps, 60 s at most) until
        `capture gif` runs again, then write DIR/recording-%Y%m%d-%H%M%S/
        with recording.gif (every frame), sheet.png (the frames that differ,
        tiled and timed, for an AI; sheet-1.png, sheet-2.png, ... when they
        need several) and frames/ (those frames at full size), and print the
        folder's path. --copy puts file://<path> of the GIF and then of the
        sheets (one list) on the clipboard (text/uri-list), so the sheets are
        on top and the GIF is next in the history. Exit codes as for region.
        DIR defaults to $XDG_PICTURES_DIR/recordings.
  capture gif --cancel
        stop a recording and throw it away (exit 1 with none going).

The frames are grabbed with wlr-screencopy (screencopy.py, stdlib) before GTK
is even imported, so nothing of ours is on screen yet and nothing has lost
focus: that raw buffer, at physical resolution, is the frozen frame, and the
saved PNG is cut from it without any scaling. $CAPTURE_T0 (ns since the
epoch) prints how long after it the frozen frame was painted.
"""

import ctypes
import fcntl
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, _DIR)

import process  # noqa: E402
import record  # noqa: E402
import screencopy  # noqa: E402
import swayipc  # noqa: E402

USAGE = "usage: capture region [--dir DIR] [--copy]\n       capture gif [--dir DIR] [--copy] | --cancel"
_PRELOAD = "libgtk4-layer-shell.so.0"
_PID_FILE = "gtk-widgets-capture-gif.pid"


def usage():
    print(USAGE, file=sys.stderr)
    sys.exit(2)


def parse_args(argv):
    """-> (mode, dir or None, copy, cancel)."""
    args = list(argv)
    if args and args[0] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    mode = args.pop(0) if args else None
    if mode not in ("region", "gif"):
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
    return mode, directory, copy, cancel


def pictures_dir():
    """$XDG_PICTURES_DIR, from the environment or user-dirs.dirs, else ~/Pictures."""
    home = os.path.expanduser("~")
    value = os.environ.get("XDG_PICTURES_DIR")
    if not value:
        config = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
        try:
            with open(os.path.join(config, "user-dirs.dirs")) as f:
                for line in f:
                    key, _, raw = line.strip().partition("=")
                    if key == "XDG_PICTURES_DIR":
                        value = raw.strip('"').replace("$HOME", home)
        except OSError:
            pass
    if not value or not os.path.isabs(value):
        value = os.path.join(home, "Pictures")
    return value


def runtime_dir():
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return runtime if os.path.isdir(runtime) else "/tmp"


def take_lock():
    """An open fd holding the lock, or None when another capture holds it."""
    fd = os.open(os.path.join(runtime_dir(), "gtk-widgets-capture.lock"),
                 os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def load_gtk():
    """Import the GTK side. gtk4-layer-shell has to be loaded before
    libwayland-client: loading it here, global, is what LD_PRELOAD does,
    without starting the process over (the frames are in memory)."""
    ctypes.CDLL(_PRELOAD, mode=ctypes.RTLD_GLOBAL)
    before = os.environ.get("LD_PRELOAD")
    os.environ["LD_PRELOAD"] = _PRELOAD  # lib/widget_base re-executes without it
    try:
        import app
    finally:
        if before is None:
            del os.environ["LD_PRELOAD"]
        else:
            os.environ["LD_PRELOAD"] = before
    return app


def free_path(directory, stamp, prefix="screenshot", suffix=".png"):
    base = os.path.join(directory, f"{prefix}-{stamp}")
    path, n = base + suffix, 1
    while os.path.lexists(path):
        n += 1
        path = f"{base}-{n}{suffix}"
    return path


def copy_uri(*paths):
    # wl-copy stays behind to serve the clipboard: keep it off our stdout, or
    # a caller reading it ($(capture region)) would wait for it to exit
    try:
        subprocess.run(["wl-copy", "-t", "text/uri-list",
                        "\r\n".join(Path(p).as_uri() for p in paths)],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"capture: copying to the clipboard failed: {e}", file=sys.stderr)
        return False
    return True


def copy_paths(gif, sheets):
    """file://<path> of the GIF, then of the sheets in one list (text/uri-list,
    as for region), so the sheets are the newest clipboard item and the GIF
    the one below it. The history (cliphist) only keeps the GIF if it has
    stored it before the sheets replace it (`wl-paste --watch` skips an item
    replaced before it read it): wait for it, 2 s at most. Without cliphist
    the wait times out and the sheets are still copied."""
    before = _cliphist_top()
    if copy_uri(gif) and before is not None:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            time.sleep(0.05)
            if _cliphist_top() != before:
                break
    copy_uri(*sheets)


def _cliphist_top():
    """cliphist's newest entry, "" for none, None without cliphist."""
    try:
        r = subprocess.run(["cliphist", "list"], stdin=subprocess.DEVNULL,
                           capture_output=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.split(b"\n", 1)[0]


def pid_path():
    return os.path.join(runtime_dir(), _PID_FILE)


def write_pid():
    tmp = pid_path() + ".new"
    with open(tmp, "w") as f:
        f.write(f"{os.getpid()}\n")
    os.replace(tmp, pid_path())


def remove_pid():
    try:
        with open(pid_path()) as f:
            if f.read().strip() != str(os.getpid()):
                return
        os.remove(pid_path())
    except (OSError, ValueError):
        pass


def signal_recorder(cancel):
    """The lock is taken: when a recording holds it, stop it (SIGUSR1) or
    throw it away (SIGUSR2, --cancel) and exit 0 quietly; else another
    capture is open."""
    try:
        with open(pid_path()) as f:
            pid = int(f.read().strip())
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            argv = f.read().split(b"\0")
        # a pid file left by a killed recording may name another process now
        if b"gif" in argv and any(os.path.basename(a) in (b"capture", b"main.py") for a in argv):
            os.kill(pid, signal.SIGUSR2 if cancel else signal.SIGUSR1)
            return 0
    except (OSError, ValueError):
        pass
    if not cancel:
        print("capture: another capture is open", file=sys.stderr)
    return 1


def fail(message):
    print(f"capture: {message}", file=sys.stderr)
    return 2


def main_region(directory, copy):
    t0 = os.environ.pop("CAPTURE_T0", None)
    lock = take_lock()
    if lock is None:
        print("capture: another capture is open", file=sys.stderr)
        return 1
    stamp = time.strftime("%Y%m%d-%H%M%S")
    try:
        frames = screencopy.capture_outputs()
    except (screencopy.CaptureError, OSError) as e:
        return fail(e)
    scales = swayipc.output_scales()
    if t0:
        t0 = int(t0)
        print(f"capture: {len(frames)} output(s) grabbed {(time.time_ns() - t0) / 1e6:.1f} ms"
              " after launch", file=sys.stderr, flush=True)

    app = load_gtk()
    result = app.pick_region(frames, scales, t0)
    if result is None:
        return 1
    picture, rect = result

    directory = os.path.abspath(os.path.expanduser(
        directory or os.path.join(pictures_dir(), "screenshots")))
    try:
        os.makedirs(directory, exist_ok=True)
        path = free_path(directory, stamp)
        app.image.save_png(picture.crop(*rect), path)
    except (OSError, ValueError) as e:
        return fail(e)
    print(path, flush=True)
    if copy:
        copy_uri(path)
    return 0


def main_gif(directory, copy, cancel):
    lock = take_lock()
    if lock is None:
        return signal_recorder(cancel)
    if cancel:
        return 1  # no recording going
    missing = [tool for tool in ("wf-recorder", "ffmpeg", "ffprobe") if not shutil.which(tool)]
    if missing:
        return fail(f"gif needs {', '.join(missing)}")
    try:
        frames = screencopy.capture_outputs()
    except (screencopy.CaptureError, OSError) as e:
        return fail(e)
    outputs = swayipc.outputs()

    app = load_gtk()
    result = app.pick_region(frames, {name: o.scale for name, o in outputs.items()})
    if result is None:
        return 1
    picture, rect = result
    name = picture.output.name
    out = outputs.get(name)
    if out is None:
        return fail(f"gif needs sway's output layout for {name!r} (is $SWAYSOCK set?)")
    if out.transform != "normal" or any(f.y_invert for f in frames if f.output.name == name):
        return fail("gif can't record a rotated or flipped output")
    try:
        plan = record.plan(rect, out.scale, out.rect[2:])
    except ValueError as e:
        return fail(e)
    if plan.rect != tuple(rect):
        print(f"capture: the output's far edge can't be recorded at scale {out.scale}:"
              f" recording {plan.rect[2]}x{plan.rect[3]} of {rect[2]}x{rect[3]}", file=sys.stderr)

    # The first frame must not show the picker: the compositor has handled
    # its unmap after the roundtrip, and a screencopy returns only once it
    # has rendered a frame since
    app.wait_unmapped()
    try:
        screencopy.capture_outputs()
    except (screencopy.CaptureError, OSError) as e:
        return fail(e)

    directory = os.path.abspath(os.path.expanduser(
        directory or os.path.join(pictures_dir(), "recordings")))
    try:
        os.makedirs(directory, exist_ok=True)
        folder = free_path(directory, time.strftime("%Y%m%d-%H%M%S"), "recording", "")
        os.mkdir(folder)
    except OSError as e:
        return fail(e)
    rec = record.Recorder(record.command(name, out.rect[:2], plan,
                                         os.path.join(folder, process.RAW)))

    def work():
        error = rec.region_error()
        if error:
            return process.ProcessError(error)
        try:
            return process.process(folder, out.scale)
        except (process.ProcessError, OSError) as e:
            return e

    try:
        rec.start()
        outcome, result = app.record(name, plan.rect, out.scale, rec, record.MAX_SECONDS,
                                     work, write_pid, remove_pid)
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
        return 1
    if outcome != "stopped":
        shutil.rmtree(folder, ignore_errors=True)
        log = rec.output().strip().splitlines()[-5:]
        return fail("wf-recorder stopped by itself: " + " / ".join(log))
    if isinstance(result, Exception):
        fail(result)
        return fail(f"the recording is kept in {folder}; retry with"
                    f" python3 {os.path.join(_DIR, 'process.py')} {folder} {out.scale}")
    print(folder, flush=True)
    if copy:
        copy_paths(os.path.join(folder, process.GIF), result["sheets"])
    return 0


def main():
    mode, directory, copy, cancel = parse_args(sys.argv[1:])
    if mode == "gif":
        return main_gif(directory, copy, cancel)
    return main_region(directory, copy)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
