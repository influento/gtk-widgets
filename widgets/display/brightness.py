#!/usr/bin/env python3
"""Brightness backend shared by the display popup and the CLI.

Backends, tried in order: laptop backlight (brightnessctl), then external
monitor via DDC/CI (ddcutil). Stdlib only so the CLI path stays fast enough
for a keybinding — no GTK import.

CLI usage (symlinked as `display-brightness`):
  display-brightness up [STEP]     raise by STEP percent (default 5)
  display-brightness down [STEP]   lower by STEP percent (default 5)
  display-brightness set PCT       set to PCT percent
  display-brightness get           print current percent
"""

import subprocess
import sys

STEP = 5
_TAG = "gtk-widgets-brightness"


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def detect_backend():
    """Return 'backlight', 'ddc', or None."""
    try:
        if _run(["brightnessctl", "-c", "backlight", "info"]).returncode == 0:
            return "backlight"
    except FileNotFoundError:
        pass
    try:
        if _run(["ddcutil", "getvcp", "10"]).returncode == 0:
            return "ddc"
    except FileNotFoundError:
        pass
    return None


def get(backend):
    """Current brightness as an integer percent (100 on failure)."""
    if backend == "backlight":
        try:
            cur = int(_run(["brightnessctl", "-c", "backlight", "get"]).stdout.strip())
            mx = int(_run(["brightnessctl", "-c", "backlight", "max"]).stdout.strip())
            return round(cur * 100 / mx)
        except Exception:
            return 100
    try:
        for part in _run(["ddcutil", "getvcp", "10"]).stdout.split(","):
            if "current value" in part:
                return int(part.split("=")[1].strip())
    except Exception:
        pass
    return 100


def set_pct(backend, pct):
    pct = max(0, min(100, int(pct)))
    if backend == "backlight":
        _run(["brightnessctl", "-c", "backlight", "set", f"{pct}%"])
    else:
        _run(["ddcutil", "setvcp", "10", str(pct)])
    return pct


def adjust(backend, delta):
    """Step brightness by delta percent, snapped to the step grid."""
    cur = get(backend)
    step = abs(delta) or STEP
    snapped = round(cur / step) * step
    return set_pct(backend, snapped + delta)


def notify(pct):
    """Transient OSD-style notification; replaces the previous one in place."""
    try:
        subprocess.Popen(
            ["notify-send", "-a", "display", "-t", "1500",
             "-h", f"string:x-canonical-private-synchronous:{_TAG}",
             "-h", f"int:value:{pct}", "Brightness", f"{pct}%"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


def main(argv):
    if not argv or argv[0] not in ("up", "down", "set", "get"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    backend = detect_backend()
    if backend is None:
        print("no brightness backend (brightnessctl/ddcutil)", file=sys.stderr)
        return 1
    cmd = argv[0]
    if cmd == "get":
        print(get(backend))
        return 0
    if cmd == "set":
        if len(argv) < 2:
            print("set: missing percent", file=sys.stderr)
            return 2
        pct = set_pct(backend, argv[1])
    else:
        step = int(argv[1]) if len(argv) > 1 else STEP
        pct = adjust(backend, step if cmd == "up" else -step)
    notify(pct)
    print(pct)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
