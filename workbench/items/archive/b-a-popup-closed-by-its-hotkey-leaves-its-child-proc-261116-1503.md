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

The popup dies without running `do_shutdown` because `WidgetPopup` installs no
SIGTERM handler, and `widget-toggle` closes a popup with SIGTERM: Python's
default for SIGTERM ends the process at once. Esc calls `quit()`, which runs
`do_shutdown`, and there bluetooth and usb stop their child. audio and display
each installed their own SIGTERM handler; the fix moves that one handler into
`WidgetPopup`, so every popup quits on SIGTERM as on Esc.

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

### Tests, before the fix

`tests/widget_toggle_test.py`: `test_usb_toggle_stops_its_udev_monitor` covers
step 1 and `test_bluetooth_toggle_stops_its_scan` step 2. Each runs
`widget-toggle` from the repository, with a fake HOME that holds install.sh's
launchers, on conftest's headless Sway; usb runs the real `udevadm monitor`,
bluetooth a fake `bluetoothctl` on PATH and a virtual-pointer click on Scan.
Run on the unfixed code, 2026-11-16 (both fail on the child that still runs):

```
$ uv run pytest -c pytest.toml tests/widget_toggle_test.py
============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0
Using --randomly-seed=2544577728
rootdir: /home/crisp/dev/infra/gtk-widgets/.worktrees/b-a-popup-closed-by-its-hotkey-leaves-its-child-proc-261116-1503
configfile: pytest.toml
plugins: timeout-2.4.0, asyncio-1.5.0, randomly-5.1.0
timeout: 60.0s
timeout method: signal
timeout func_only: False
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collected 2 items

tests/widget_toggle_test.py FF                                           [100%]

=================================== FAILURES ===================================
_____________________ test_bluetooth_toggle_stops_its_scan _____________________

tmp_path = PosixPath('/tmp/pytest-of-crisp/pytest-15/test_bluetooth_toggle_stops_it0')

    def test_bluetooth_toggle_stops_its_scan(tmp_path: Path) -> None:
        desk = Desktop(tmp_path)
        desk.install("bluetooth", "bluetooth")
        desk.fake("bluetoothctl", FAKE_BLUETOOTHCTL)
        desk.toggle("bluetooth")
        pid = desk.widget_pid("bluetooth")
        last_click = 0.0
    
        def press_scan() -> None:
            nonlocal last_click
            if time.monotonic() - last_click >= CLICK_RETRY:
                last_click = time.monotonic()
                click(*SCAN_BUTTON)
    
        child = wait_child(pid, "--timeout 10 scan on", press_scan)
        try:
            desk.toggle("bluetooth")
>           assert_closed_with_child("bluetooth", pid, child)

tests/widget_toggle_test.py:206: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

widget = 'bluetooth', pid = 998690
child = (998777, 'python3 /tmp/pytest-of-crisp/pytest-15/test_bluetooth_toggle_stops_it0/fakes/bluetoothctl --timeout 10 scan on')

    def assert_closed_with_child(widget: str, pid: int, child: tuple[int, str]) -> None:
        deadline = time.monotonic() + CLOSE_TIMEOUT
        while cmdline(pid) or cmdline(child[0]) == child[1]:
            if time.monotonic() > deadline:
                break
            time.sleep(POLL)
        assert not cmdline(pid), f"{widget} is still open after the second widget-toggle"
        left = cmdline(child[0])
>       assert left != child[1], f"{widget}'s child still runs after its close: {left}"
E       AssertionError: bluetooth's child still runs after its close: python3 /tmp/pytest-of-crisp/pytest-15/test_bluetooth_toggle_stops_it0/fakes/bluetoothctl --timeout 10 scan on
E       assert 'python3 /tmp/pytest-of-crisp/pytest-15/test_bluetooth_toggle_stops_it0/fakes/bluetoothctl --timeout 10 scan on' != 'python3 /tmp/pytest-of-crisp/pytest-15/test_bluetooth_toggle_stops_it0/fakes/bluetoothctl --timeout 10 scan on'

tests/widget_toggle_test.py:171: AssertionError
____________________ test_usb_toggle_stops_its_udev_monitor ____________________

tmp_path = PosixPath('/tmp/pytest-of-crisp/pytest-15/test_usb_toggle_stops_its_udev0')

    def test_usb_toggle_stops_its_udev_monitor(tmp_path: Path) -> None:
        desk = Desktop(tmp_path)
        desk.install("usb", "usb")
        desk.toggle("usb")
        pid = desk.widget_pid("usb")
        child = wait_child(pid, "udevadm monitor --subsystem-match=block")
        try:
            desk.toggle("usb")
>           assert_closed_with_child("usb", pid, child)

tests/widget_toggle_test.py:182: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

widget = 'usb', pid = 998956
child = (998964, 'udevadm monitor --subsystem-match=block --udev')

    def assert_closed_with_child(widget: str, pid: int, child: tuple[int, str]) -> None:
        deadline = time.monotonic() + CLOSE_TIMEOUT
        while cmdline(pid) or cmdline(child[0]) == child[1]:
            if time.monotonic() > deadline:
                break
            time.sleep(POLL)
        assert not cmdline(pid), f"{widget} is still open after the second widget-toggle"
        left = cmdline(child[0])
>       assert left != child[1], f"{widget}'s child still runs after its close: {left}"
E       AssertionError: usb's child still runs after its close: udevadm monitor --subsystem-match=block --udev
E       assert 'udevadm monitor --subsystem-match=block --udev' != 'udevadm monitor --subsystem-match=block --udev'

tests/widget_toggle_test.py:171: AssertionError
=========================== short test summary info ============================
FAILED tests/widget_toggle_test.py::test_bluetooth_toggle_stops_its_scan - As...
FAILED tests/widget_toggle_test.py::test_usb_toggle_stops_its_udev_monitor - ...
============================== 2 failed in 11.68s ==============================
```

The first repro script (`check.sh` above) was in another session's scratchpad
and is gone; it also ran the main checkout's installed launchers, not this
branch. The tests run the same path against the branch's code.

### Demo, 2026-11-16

Run by wb-demo on the user's desktop, with the user watching. The installed
`~/.local/bin` launchers run the main checkout's `src/`, so, as the user chose
("Your desktop, branch code"), the worktree's `widget-toggle` ran with `HOME`
set to a temporary directory (`/tmp/tmp.5bo2VEwGn5`) whose `.local/bin/usb` and
`.local/bin/bluetooth` are install.sh-style launchers of this branch's `src/`:

```
#!/usr/bin/env python3
import sys
sys.path.insert(0, "/home/crisp/dev/infra/gtk-widgets/.worktrees/b-a-popup-closed-by-its-hotkey-leaves-its-child-proc-261116-1503/src")
from gtk_widgets.widgets.usb.main import main
sys.exit(main())
```

The pgrep of each step ran from a script file (`pg-usb.sh`, `pg-bt.sh` in
wb-demo's scratchpad, holding only the echo and the pgrep line shown in the
output), because a pgrep typed in the agent's shell also matches that shell,
whose command line holds the pattern.

#### Step 1 (usb)

```
$ H=/tmp/tmp.5bo2VEwGn5; WT=$PWD/widget-toggle
$ HOME=$H "$WT" usb; sleep 4
$ echo "--- open: widget pid $(cat /run/user/1000/gtk-widgets-usb-toggle.pid), its children:"; pgrep -aP "$(cat /run/user/1000/gtk-widgets-usb-toggle.pid)"
$ HOME=$H "$WT" usb; sleep 1.5
$ pgrep -af 'udevadm monitor --subsystem-match=block'; echo "exit $?"
$ ls /run/user/1000/gtk-widgets-usb-toggle.pid 2>&1
--- open: widget pid 2545597, its children:
2545616 udevadm monitor --subsystem-match=block --udev
--- $ pgrep -af 'udevadm monitor --subsystem-match=block'
2545591 /usr/bin/zsh -c source /home/crisp/.claude/shell-snapshots/snapshot-zsh-1794856256987-g7cxy9.sh 2>/dev/null || true && \builtin setopt NO_EXTENDED_GLOB NO_BARE_GLOB_QUAL NO_BRACE_CCL NO_MAGIC_EQUAL_SUBST 2>/dev/null || true && { \builtin unalias -- 'which'; \builtin unset -f -- 'which'; } >/dev/null 2>&1 || true && { \builtin unalias -- 'unsetenv'; \builtin unset -f -- 'unsetenv'; } >/dev/null 2>&1 || true && eval 'H=/tmp/tmp.5bo2VEwGn5; WT=$PWD/widget-toggle HOME=$H "$WT" usb; sleep 4 echo "--- open: widget pid $(cat /run/user/1000/gtk-widgets-usb-toggle.pid), its children:"; pgrep -aP "$(cat /run/user/1000/gtk-widgets-usb-toggle.pid)" HOME=$H "$WT" usb; sleep 1.5 echo "--- \$ pgrep -af '"'"'udevadm monitor --subsystem-match=block'"'"'" pgrep -af '"'"'udevadm monitor --subsystem-match=block'"'"'; echo "exit $?" ls /run/user/1000/gtk-widgets-usb-toggle.pid 2>&1' < /dev/null && pwd -P >| /tmp/claude-8629-cwd
exit 0
ls: cannot access '/run/user/1000/gtk-widgets-usb-toggle.pid': No such file or directory
```

The one match is the agent's own shell (2545591), not udevadm. The pgrep
again, from the script file, and the udevadm the popup started:

```
$ bash "$SP/pg-usb.sh"; ps -o pid,ppid,args -p 2545616; echo "ps exit $?"
$ pgrep -af 'udevadm monitor --subsystem-match=block'
exit 1
--- the udevadm the popup started (2545616):
    PID    PPID COMMAND
ps exit 1
```

wb-demo's near case (not a step): close 0.5 s and 1 s after the open:

```
$ for d in 0.5 1; do echo "== close after $d s"; HOME=$H "$WT" usb; sleep $d; p=$(cat /run/user/1000/gtk-widgets-usb-toggle.pid); echo "widget $p children: $(pgrep -aP "$p")"; HOME=$H "$WT" usb; sleep 1.5; echo "widget alive: $(kill -0 "$p" 2>/dev/null && echo yes || echo no)"; bash "$SP/pg-usb.sh"; done
== close after 0.5 s
widget 2548717 children: 2548740 udevadm monitor --subsystem-match=block --udev
widget alive: no
$ pgrep -af 'udevadm monitor --subsystem-match=block'
exit 1
== close after 1 s
widget 2548831 children: 2548869 udevadm monitor --subsystem-match=block --udev
widget alive: no
$ pgrep -af 'udevadm monitor --subsystem-match=block'
exit 1
```

wb-demo: PASS. pgrep prints nothing (exit 1). The popup had `udevadm monitor
--subsystem-match=block --udev` as its child while open; after the second
`widget-toggle` the popup, its udevadm and the pid file are gone. The near
case also leaves nothing.

The user, 2026-11-16: "PASS".

#### Step 2 (bluetooth)

First try: wb-demo opened the popup and asked the user to click Scan, then
answer; the user answered "run it once again", and the popup was already
closed with no scan running:

```
$ HOME=/tmp/tmp.5bo2VEwGn5 "$PWD/widget-toggle" bluetooth; sleep 2; p=$(cat /run/user/1000/gtk-widgets-bluetooth-toggle.pid); echo "widget pid $p"; ps -o pid,args -p "$p"
widget pid 2554365
    PID COMMAND
2554365 python3 /tmp/tmp.5bo2VEwGn5/.local/bin/bluetooth
$ p=2554365; ps -o pid,args -p $p; pgrep -aP $p; echo; bash "$SP/pg-bt.sh"
    PID COMMAND

$ pgrep -af 'bluetoothctl --timeout 10 scan on'
exit 1
```

Second try: the command waits for the scan the user's click starts, then
closes the popup 2 s later. The user clicked "Scan for devices":

```
$ H=/tmp/tmp.5bo2VEwGn5; WT=$PWD/widget-toggle
$ HOME=$H "$WT" bluetooth; sleep 1; p=$(cat /run/user/1000/gtk-widgets-bluetooth-toggle.pid); echo "widget pid $p: $(ps -o args= -p "$p")"
$ k=; for _ in $(seq 600); do k=$(pgrep -f -P "$p" 'scan on') && break; kill -0 "$p" 2>/dev/null || { echo "popup closed before a scan"; break; }; sleep 0.1; done
$ if [[ -n "$k" ]]; then echo "scan started, popup's children:"; pgrep -aP "$p"; sleep 2
    HOME=$H "$WT" bluetooth; sleep 1.5
    echo "widget alive: $(kill -0 "$p" 2>/dev/null && echo yes || echo no)"
    bash "$SP/pg-bt.sh"
    echo "--- the scan child ($k):"; ps -o pid,ppid,args -p "$k"; echo "ps exit $?"
  fi
widget pid 2557298: python3 /tmp/tmp.5bo2VEwGn5/.local/bin/bluetooth
scan started, popup's children:
2557493 bluetoothctl --timeout 10 scan on
widget alive: no
$ pgrep -af 'bluetoothctl --timeout 10 scan on'
exit 1
--- the scan child (2557493):
    PID    PPID COMMAND
ps exit 1
```

wb-demo's near case (not a step): the adapter after the stopped scan:

```
$ bluetoothctl show | grep -E 'Powered|Discovering'
	Powered: yes
	Discovering: no
```

wb-demo: PASS. pgrep prints nothing (exit 1). The real `bluetoothctl
--timeout 10 scan on` the click started was the popup's child; the second
`widget-toggle`, about 3.5 s after the scan started, closed the popup and the
scan went with it, before its own 10 s timeout. The adapter is not left
discovering.

The user, 2026-11-16: "PASS".

#### Decisions and backlog

The proof records no decision for a case that no step covers. The branch adds
no entry to `workbench/BACKLOG.md` (translate's entry is on main, commit
99c5eec, before the branch).

### wb-tester on 289846c, 2026-11-17

#### `widget-toggle usb`, then `widget-toggle usb`, then `pgrep -af 'udevadm monitor --subsystem-match=block'` prints nothing.

PASS: The popup had `udevadm monitor --subsystem-match=block --udev` (879998) as its child, and after the second widget-toggle the popup and that udevadm were both gone (ps exit 1). pgrep's one match was my own tester shell (879982): its command line held the pattern text from an echo in the harness. It was not a udevadm, so no udevadm monitor was left running.

~~~
$ T=/tmp/tmp.x2tdfIixh4 R=/run/user/1000/tmp.Fij91reLGJ
export HOME_T="$T/home"
run() { env -u DISPLAY -u I3SOCK HOME="$T/home" XDG_RUNTIME_DIR="$R" WAYLAND_DISPLAY=wayland-1 SWAYSOCK="$R/sway.sock" GDK_BACKEND=wayland PATH="$T/fakes:$PATH" DBUS_SESSION_BUS_ADDRESS=unix:path=/nonexistent "$@"; }
echo '$ widget-toggle usb'; run ./widget-toggle usb; sleep 4
p=$(cat "$R/gtk-widgets-usb-toggle.pid"); echo "(open: widget $p, children:)"; pgrep -aP "$p"
echo '$ widget-toggle usb'; run ./widget-toggle usb; sleep 1.5
echo "(widget alive: $(kill -0 "$p" 2>/dev/null && echo yes || echo no))"
echo "\$ pgrep -af 'udevadm monitor --subsystem-match=block'"; bash "$T/pg-usb.sh"; echo "exit $?"
# then:
ps -o pid,ppid,args -p 879998; echo "ps exit $?"; ps -o pid,args -p 879982; echo "ps exit $?"

(Run on a private headless Sway (pid 879375, own XDG_RUNTIME_DIR) with the worktree's widget-toggle and a fake HOME whose ~/.local/bin/usb is an install.sh-style launcher of this worktree's src/. $T/pg-usb.sh holds only: pgrep -af udevadm\ monitor\ --subsystem-match=block)
$ widget-toggle usb
(open: widget 879988, children:)
879998 udevadm monitor --subsystem-match=block --udev
$ widget-toggle usb
(widget alive: no)
$ pgrep -af 'udevadm monitor --subsystem-match=block'
879982 /usr/bin/zsh -c source /home/crisp/.claude/shell-snapshots/snapshot-zsh-1794875819914-t6q8dc.sh 2>/dev/null || true && \builtin setopt NO_EXTENDED_GLOB NO_BARE_GLOB_QUAL NO_BRACE_CCL NO_MAGIC_EQUAL_SUBST 2>/dev/null || true && { \builtin unalias -- 'which'; \builtin unset -f -- 'which'; } >/dev/null 2>&1 || true && { \builtin unalias -- 'unsetenv'; \builtin unset -f -- 'unsetenv'; } >/dev/null 2>&1 || true && eval 'T=/tmp/tmp.x2tdfIixh4 R=/run/user/1000/tmp.Fij91reLGJ export HOME_T="$T/home" run() { env -u DISPLAY -u I3SOCK HOME="$T/home" XDG_RUNTIME_DIR="$R" WAYLAND_DISPLAY=wayland-1 SWAYSOCK="$R/sway.sock" GDK_BACKEND=wayland PATH="$T/fakes:$PATH" DBUS_SESSION_BUS_ADDRESS=unix:path=/nonexistent "$@"; } echo '"'"'$ widget-toggle usb'"'"'; run ./widget-toggle usb; sleep 4 p=$(cat "$R/gtk-widgets-usb-toggle.pid"); echo "(open: widget $p, children:)"; pgrep -aP "$p" echo '"'"'$ widget-toggle usb'"'"'; run ./widget-toggle usb; sleep 1.5 echo "(widget alive: $(kill -0 "$p" 2>/dev/null && echo yes || echo no))" echo "\$ pgrep -af '"'"'udevadm monitor --subsystem-match=block'"'"'"; bash "$T/pg-usb.sh"; echo "exit $?"' < /dev/null && pwd -P >| /tmp/claude-f478-cwd
exit 0
--- then:
    PID    PPID COMMAND
ps exit 1
    PID COMMAND
ps exit 1
~~~

#### `widget-toggle bluetooth`, click "Scan for devices", then `widget-toggle bluetooth`, then `pgrep -af 'bluetoothctl --timeout 10 scan on'` prints nothing.

PASS: The click on Scan started `bluetoothctl --timeout 10 scan on` as the popup's child. The second widget-toggle closed the popup about 2 s later, well before the scan's 10 s timeout, and pgrep printed nothing (exit 1). The scan child is gone.

~~~
$ bash "$T/step2.sh" "$T" "$R" "$PWD"

step2.sh:
#!/usr/bin/env bash
T="$1" R="$2" WT="$3"
run() { env -u DISPLAY -u I3SOCK HOME="$T/home" XDG_RUNTIME_DIR="$R" WAYLAND_DISPLAY=wayland-1 SWAYSOCK="$R/sway.sock" GDK_BACKEND=wayland PATH="$T/fakes:$PATH" DBUS_SESSION_BUS_ADDRESS=unix:path=/nonexistent "$@"; }
echo '$ widget-toggle bluetooth'; run "$WT/widget-toggle" bluetooth; sleep 1
for _ in $(seq 100); do p=$(cat "$R/gtk-widgets-bluetooth-toggle.pid" 2>/dev/null) && [[ -n "$p" ]] && break; sleep 0.1; done
echo "(widget $p: $(ps -o args= -p "$p"))"
echo '(click "Scan for devices" at 640,121 until the scan child starts)'
k=
for _ in $(seq 30); do
  k=$(pgrep -P "$p" -f 'scan on') && break
  run env PYTHONPATH="$WT/src" python3 "$T/click.py" 640 121
  sleep 0.5
done
echo "(scan child: $(pgrep -aP "$p"))"
echo '$ widget-toggle bluetooth'; run "$WT/widget-toggle" bluetooth; sleep 1.5
echo "(widget alive: $(kill -0 "$p" 2>/dev/null && echo yes || echo no))"
echo "\$ pgrep -af '$(sed -n 2p "$T/pg-bt.sh" | cut -c11-)'"
bash "$T/pg-bt.sh"; echo "exit $?"
echo "(scan child $k:)"; ps -o pid,ppid,args -p "$k"; echo "ps exit $?"

(The same private headless Sway and fake HOME. bluetoothctl is the test's fake on PATH: `show` reports a powered adapter, `scan on` sleeps for its --timeout. click.py is a zwlr_virtual_pointer click, as in the Proof. pg-bt.sh holds only: pgrep -af bluetoothctl\ --timeout\ 10\ scan\ on)
$ widget-toggle bluetooth
(widget 881246: python3 /tmp/tmp.x2tdfIixh4/home/.local/bin/bluetooth)
(click "Scan for devices" at 640,121 until the scan child starts)
(scan child: 881298 python3 /tmp/tmp.x2tdfIixh4/fakes/bluetoothctl --timeout 10 scan on)
$ widget-toggle bluetooth
(widget alive: no)
$ pgrep -af 'bluetoothctl\ --timeout\ 10\ scan\ on'
exit 1
(scan child 881298:)
    PID    PPID COMMAND
ps exit 1
~~~
