#!/usr/bin/env python3
"""capture — screenshots at the output's own pixels.

  capture region [--dir DIR] [--copy]
        freeze every output, drag a rectangle, save it as
        DIR/screenshot-%Y%m%d-%H%M%S.png and print the file's absolute path;
        --copy also puts file://<path> on the clipboard (text/uri-list).
        Exit 0 on save; 1 when cancelled (Esc, right click) or when another
        capture is open, with no file; 2 on errors.
        DIR defaults to $XDG_PICTURES_DIR/screenshots.

The frames are grabbed with wlr-screencopy (screencopy.py, stdlib) before GTK
is even imported, so nothing of ours is on screen yet and nothing has lost
focus: that raw buffer, at physical resolution, is the frozen frame, and the
saved PNG is cut from it without any scaling. $CAPTURE_T0 (ns since the
epoch) prints how long after it the frozen frame was painted.
"""

import ctypes
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, _DIR)

import screencopy  # noqa: E402
import swayipc  # noqa: E402

USAGE = "usage: capture region [--dir DIR] [--copy]"


def usage():
    print(USAGE, file=sys.stderr)
    sys.exit(2)
_PRELOAD = "libgtk4-layer-shell.so.0"


def parse_args(argv):
    """-> (mode, dir or None, copy)."""
    args = list(argv)
    if args and args[0] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    if not args or args.pop(0) != "region":
        usage()
    directory, copy = None, False
    while args:
        arg = args.pop(0)
        if arg == "--dir" and args:
            directory = args.pop(0)
        elif arg.startswith("--dir="):
            directory = arg.split("=", 1)[1]
        elif arg == "--copy":
            copy = True
        else:
            usage()
    if directory == "":
        usage()
    return "region", directory, copy


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


def take_lock():
    """An open fd holding the lock, or None when another capture holds it."""
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    if not os.path.isdir(runtime):
        runtime = "/tmp"
    fd = os.open(os.path.join(runtime, "gtk-widgets-capture.lock"),
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


def free_path(directory, stamp):
    base = os.path.join(directory, f"screenshot-{stamp}")
    path, n = base + ".png", 1
    while os.path.lexists(path):
        n += 1
        path = f"{base}-{n}.png"
    return path


def copy_uri(path):
    # wl-copy stays behind to serve the clipboard: keep it off our stdout, or
    # a caller reading it ($(capture region)) would wait for it to exit
    try:
        subprocess.run(["wl-copy", "-t", "text/uri-list", Path(path).as_uri()],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"capture: copying to the clipboard failed: {e}", file=sys.stderr)


def main():
    _mode, directory, copy = parse_args(sys.argv[1:])
    t0 = os.environ.pop("CAPTURE_T0", None)
    lock = take_lock()
    if lock is None:
        print("capture: another capture is open", file=sys.stderr)
        return 1
    stamp = time.strftime("%Y%m%d-%H%M%S")
    try:
        frames = screencopy.capture_outputs()
    except (screencopy.CaptureError, OSError) as e:
        print(f"capture: {e}", file=sys.stderr)
        return 2
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
        print(f"capture: {e}", file=sys.stderr)
        return 2
    print(path, flush=True)
    if copy:
        copy_uri(path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
