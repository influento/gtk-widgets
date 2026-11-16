# b-a-popup-closed-by-its-hotkey-leaves-its-child-proc-261116-1503 — A popup closed by its hotkey leaves its child process running

## Why

Seen by the agent on 2026-11-16, while checking a review question of the
user's ("can it appear in other places as well?"): when `widget-toggle`
closes a popup a second time (the hotkey), a child process the popup started
keeps running, its parent now pid 1:

- usb: `udevadm monitor --subsystem-match=block --udev`, started when the
  popup opens, stays until something stops it.
- bluetooth: `bluetoothctl --timeout 10 scan on`, started by Scan, stays
  until its own 10 s timeout.

Closed with Esc, usb stops its monitor.

## Root cause

Not confirmed yet (the item's session finds it). Candidate from reading the
code: bluetooth and usb stop their child in `do_shutdown`, but
`widget-toggle` closes with SIGTERM, and `WidgetPopup` installs no SIGTERM
handler, so the process dies without running `do_shutdown`. audio, display,
launcher and network-agent install their own handler.

## Check

1. `widget-toggle usb`, then `widget-toggle usb`, then
   `pgrep -af 'udevadm monitor --subsystem-match=block'` prints nothing.
2. `widget-toggle bluetooth`, click "Scan for devices", then
   `widget-toggle bluetooth`, then `pgrep -af 'bluetoothctl --timeout 10 scan on'`
   prints nothing.

## Proof

### What the user said

- 2026-11-16, on how to file it: "One bug item".
- 2026-11-16, on the check: "usb, bluetooth, we can skip translate since its
  unfinished widget" (translate's `claude -p` request, left running by the
  hotkey and by Esc, is out of this item: a BACKLOG.md entry).

### Before the change

The check's steps open popups on the user's desktop, which an agent must not
use, so the agent ran them on a private headless Sway with the script below
(outside the repository, in the session's scratchpad). bluetoothctl is a fake
on PATH, so no real scan ran; usb ran the real `udevadm monitor`. The
leftovers were stopped by their pid afterwards.

`check.sh`:

```
#!/usr/bin/env bash
# Usage: check.sh SCRATCH WIDGET [setup command]: open WIDGET with widget-toggle on a
# private headless sway, show its children, close it with widget-toggle, show which live on
set -uo pipefail
S="$1" W="$2"; shift 2
rt="$(mktemp -d -p "/run/user/$(id -u)")"
export XDG_RUNTIME_DIR="$rt" PATH="$S/bin:$PATH" DBUS_SESSION_BUS_ADDRESS=unix:path=/nonexistent
unset WAYLAND_DISPLAY DISPLAY SWAYSOCK I3SOCK
printf 'output HEADLESS-1 resolution 1280x720\nxwayland disable\n' > "$rt/sway.conf"
WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman SWAYSOCK="$rt/sway.sock" \
  sway --config "$rt/sway.conf" > "$S/sway-$W.log" 2>&1 &
sway_pid=$!
trap 'kill "$sway_pid" 2>/dev/null; wait "$sway_pid" 2>/dev/null; rm -rf "$rt"' EXIT
for _ in $(seq 100); do lock="$(compgen -G "$rt/wayland-*.lock" | head -1)" && break; sleep 0.05; done
export WAYLAND_DISPLAY="$rt/$(basename "$lock" .lock)" SWAYSOCK="$rt/sway.sock" GDK_BACKEND=wayland
sleep 0.5
if (( $# )); then eval "$*"; fi
widget-toggle "$W"; sleep 4
pid="$(cat "$rt/gtk-widgets-$W-toggle.pid")"
[[ -n "${AFTER_OPEN:-}" ]] && { eval "$AFTER_OPEN"; sleep 1; }
kids="$(pgrep -P "$pid" | tr '\n' ' ')"
echo "open: widget $pid, children:"; for k in $kids; do ps -o pid=,ppid=,args= -p "$k"; done
widget-toggle "$W"; sleep 1.5
echo "widget alive after toggle: $(kill -0 "$pid" 2>/dev/null && echo yes || echo no)"
echo "children alive after toggle:"
for k in $kids; do ps -o pid=,ppid=,args= -p "$k" || true; done
[[ -n "${WLCOPY_PID:-}" ]] && kill "$WLCOPY_PID" 2>/dev/null
```

`bin/bluetoothctl` (fake):

```
#!/usr/bin/env bash
# fake: an adapter that is on; a scan runs its --timeout
case " $* " in
  *" show "*) printf 'Controller 00:00:00:00:00:01 (public)\n\tPowered: yes\n' ;;
  *" scan on "*) sleep 10 ;;
esac
```

`click.py` (a click with a wlr virtual pointer; the Scan button is at
640,121 on a 1280x720 output, seen on a screenshot):

```
"""click X Y on a 1280x720 output with a wlr virtual pointer"""
import struct, sys, time
from gtk_widgets.lib.wayland import Connection
c = Connection()
g = {i: n for n, i, _v in c.globals()}
m = c.bind(g["zwlr_virtual_pointer_manager_v1"], "zwlr_virtual_pointer_manager_v1", 1, lambda o, r: None)
p = c.new_id(lambda o, r: None)
c.send(m, 0, struct.pack("=II", 0, p))
ms = lambda: int(time.monotonic() * 1000) & 0xFFFFFFFF
x, y = int(sys.argv[1]), int(sys.argv[2])
for op, args in ((1, struct.pack("=IIIII", ms(), x * 100000 // 1280, y * 100000 // 720, 100000, 100000)),
                 (2, struct.pack("=III", ms(), 0x110, 1)), (2, struct.pack("=III", ms(), 0x110, 0))):
    c.send(p, op, args); c.send(p, 4); c.roundtrip(); time.sleep(0.05)
c.send(p, 8); c.roundtrip()
```

Step 1 (usb), 2026-11-16:

```
$ S=/tmp/claude-1000/-home-crisp-dev-infra-gtk-widgets/ee570809-e236-447c-a619-b9c6c8b1b71c/scratchpad/tmp.qGeJvXXrZ5; timeout 60 "$S/check.sh" "$S" usb
open: widget 871832, children:
 871838  871832 udevadm monitor --subsystem-match=block --udev
widget alive after toggle: no
children alive after toggle:
 871838       1 udevadm monitor --subsystem-match=block --udev
```

Step 2 (bluetooth), 2026-11-16 (the first `python3 -I` fails because `-I`
ignores PYTHONPATH; the fallback after `||` made the click):

```
$ AFTER_OPEN="PYTHONPATH=/home/crisp/dev/infra/gtk-widgets/src python3 -I $S/click.py 640 121 || PYTHONPATH=/home/crisp/dev/infra/gtk-widgets/src python3 $S/click.py 640 121" timeout 60 "$S/check.sh" "$S" bluetooth; ps -eo pid,ppid,args | grep -F "$S/bin" | grep -v grep
Traceback (most recent call last):
  File "/tmp/claude-1000/-home-crisp-dev-infra-gtk-widgets/ee570809-e236-447c-a619-b9c6c8b1b71c/scratchpad/tmp.qGeJvXXrZ5/click.py", line 3, in <module>
    from gtk_widgets.lib.wayland import Connection
ModuleNotFoundError: No module named 'gtk_widgets'
open: widget 920142, children:
 920419  920142 bash /tmp/claude-1000/-home-crisp-dev-infra-gtk-widgets/ee570809-e236-447c-a619-b9c6c8b1b71c/scratchpad/tmp.qGeJvXXrZ5/bin/bluetoothctl --timeout 10 scan on
widget alive after toggle: no
children alive after toggle:
 920419       1 bash /tmp/claude-1000/-home-crisp-dev-infra-gtk-widgets/ee570809-e236-447c-a619-b9c6c8b1b71c/scratchpad/tmp.qGeJvXXrZ5/bin/bluetoothctl --timeout 10 scan on
 920419       1 bash /tmp/claude-1000/-home-crisp-dev-infra-gtk-widgets/ee570809-e236-447c-a619-b9c6c8b1b71c/scratchpad/tmp.qGeJvXXrZ5/bin/bluetoothctl --timeout 10 scan on
```

Narrower, the same script closing with Esc (`CLOSE='wtype -s 250 -k Escape'`
in place of the second `widget-toggle`), usb, 2026-11-16: the monitor is gone
(the line under "children alive" is translate's leftover from the run before it):

```
== usb, Esc
open: widget 923371, children:
 923464  923371 udevadm monitor --subsystem-match=block --udev
widget alive after toggle: no
children alive after toggle:
 922693       1 bash /tmp/claude-1000/-home-crisp-dev-infra-gtk-widgets/ee570809-e236-447c-a619-b9c6c8b1b71c/scratchpad/tmp.qGeJvXXrZ5/bin/claude -p --model sonnet --no-session-persistence Auto-detect the source language. If the text is in Russian, translate to English. If the text is in English, translate to Russian. For any other language, translate to English. Output ONLY the translation, nothing else. No explanations, no quotes, no prefixes.
```
