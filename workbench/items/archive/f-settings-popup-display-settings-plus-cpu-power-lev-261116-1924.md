# f-settings-popup-display-settings-plus-cpu-power-lev-261116-1924 — Settings popup: display settings plus CPU power level (EPP) switching

No test: step 2 — its expected result is the kernel's own EPP files, which only root can write, through the polkit helper installed in /usr/lib/gtk-widgets; no other test of the project runs as root or through polkit. A fake pkexec or helper cannot show it: the code reads the fixed /sys/devices/system/cpu and runs the fixed /usr/lib/gtk-widgets/epp-helper (pkexec runs only that root-owned path), so a fake reaches neither without a way to redirect those paths that only tests would use, which the project's rules forbid.
No test: step 3 — it writes the kernel's own EPP files with sudo and through the polkit helper installed in /usr/lib/gtk-widgets; no other test of the project runs as root or through polkit. A fake pkexec or helper cannot show it, for the same reason as step 2: the fixed /sys and helper paths could be redirected only by code that only tests would use.

## Why

On the laptop (ASUS Zenbook S 14, Intel), the fan stays on at ~3800 RPM after
any burst until the package is below ~45 °C, and the default energy
performance preference (EPP) `balance_performance` keeps background load
above that. `balance_power` keeps idle under 45 °C, so the fan turns off
(another session's measurements, 2026-11-16). Today the only way to change
EPP is to write sysfs as root, and the value resets at reboot.

The user wants one-click EPP switching in a popup, with the pick restored
after a reboot. More quick settings will follow, so the `display` popup
becomes `settings`: its scale, brightness and night light stay as they are,
and a CPU row with the four EPP levels joins them. Root writes go through a
polkit helper (as usb and proxy do). The pick is stored like the display
settings, in `~/.local/state/dotfiles/`, and dotfiles applies it at sway
startup (the dotfiles change is outside this repo).

It must work on AMD too: crisp-desktop (Ryzen 7 8845HS, `amd-pstate-epp`,
active) offers the same EPP files and levels (checked over ssh, 2026-11-16;
there the level changes speed and temperature by 3% or less).

## Check

1. `widget-toggle settings` opens a popup with the display settings (scale,
   brightness, night light) and a CPU row of four levels: performance,
   balance_performance, balance_power, power. The current level is
   highlighted. (The user judges.)
2. In that popup, click balance_power. No password prompt shows; the
   highlight moves to it, and
   `cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort | uniq -c`
   prints one line, `<number of CPUs> balance_power`.
3. Then `echo balance_performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference`
   (what a reboot does), then the startup restore command, then the `cat`
   of step 2 prints one line, `<number of CPUs> balance_power`.

## Proof

### What the user said

- 2026-11-16, on placement: "wrap display to settings and have it there
  (consider that in future there might be more settings Id prefer to have a
  quick access to)"; "settings is fine".
- 2026-11-16, on restore: "it should be stored similar to how currently its
  stored for display settings".
- 2026-11-16, on per-machine speed/temperature numbers next to the levels:
  "I guess there is nothing to test. lets just build a simple widget then as
  we discussed it and that's it"; "Id prefer to make sure that it will
  actually work at least at some sort on crisp-desktop to make sure its not
  a thing which simply is intel specific or smth".
- 2026-11-16, on the check: "Agree" (steps 1-3). On step 4: "deliver that
  shit to this workstation I didnt ask you to deploy it there. ive asked you
  to make sure that shit built here will work make any difference there".

### Before the change (2026-11-16)

EPP on crisp-laptop was already balance_power (set by another session), so
step 2's `cat` alone would pass; step 2 fails on its popup, which does not
exist. Step 1 and step 4 (no `settings` command, no helper):

```
$ ls polkit/epp-helper; ls ~/.local/bin/settings
ls: cannot access 'polkit/epp-helper': No such file or directory
ls: cannot access '/home/crisp/.local/bin/settings': No such file or directory
```

Step 3 (the restore command name is the one this item adds):

```
$ echo balance_performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference; settings-epp restore; cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort | uniq -c
balance_performance
(eval):1: command not found: settings-epp
      8 balance_performance
```

EPP was then set back to balance_power by hand.

### Decisions on cases the check has no step for

- The `display` command becomes `settings` (`settings-status`, application id
  `dev.dotfiles.settings`); `display-brightness` keeps its name, since dotfiles'
  sway config binds it. dotfiles must switch waybar's `custom/display` to
  `settings-status` / `widget-toggle settings` and add
  `exec ~/.local/bin/settings-epp restore` at sway startup (outside this repo).
- `install.sh` removes, from `~/.local/bin`, a launcher it wrote (it names this
  checkout's `src/`) for a command pyproject no longer lists (`display`) and a
  dead link into this checkout (`display-status` after the merge), so a renamed
  command leaves nothing broken there; other files stay. This is the backlog
  entry "install.sh: remove stale entries in ~/.local/bin" (the user's pick of
  ownership over a manifest, 2026-11-14), so the entry is deleted:

```
$ (throwaway HOME: a `display` launcher naming this src/, a `display-status` link into
   this checkout, a launcher naming /elsewhere/src, a dead link to /nonexistent, a user file;
   sudo stubbed to fail) HOME=$h PATH=$b:$PATH bash install.sh 2>&1 | grep -E "removed|display|settings"; ls $h/.local/bin
  display-brightness
  settings
  settings-epp
  removed: display
  removed: display-status
  settings-status
audio bluetooth bluetooth-status calendar calendar-status capture claude-usage claude-usage-status display-brightness foreign-dead-link launcher launcher-clipboard network network-agent network-status other-checkout power power-status settings settings-epp settings-status timer timer-status translate usb usb-status userscript widget-toggle
```
 Old tests changed for the rename (the item's
  Why: "the `display` popup becomes `settings`"): `tests/repro-display-state.sh`
  imports `gtk_widgets.widgets.settings`; `tests/smoke/inner.sh` runs `settings`
  and `settings-status` in place of `display` and `display-status`, and adds
  `settings-epp restore` (no stored pick: exit 0).
- The popup keeps its "Display" title and gets a "CPU" group below night light
  with a POWER LEVEL row of four buttons named as the kernel names them. It is
  wider than before (~428 px against ~330 px) to fit the four names in one row.
- No EPP files (another cpufreq driver): the CPU group is not shown.
- CPUs at different levels: no button is highlighted.
- A click disables the four buttons until the helper returns; then the
  highlight follows what the kernel files say. A failure (pkexec refused, the
  helper missing, EBUSY under the performance governor) shows on a copyable
  error line under the row, and the pick is not stored.
- `settings-epp restore`: nothing stored → exit 0, does nothing; a stored text
  that is not one of the four levels or a helper failure → the reason on
  stderr, exit 1; other arguments → usage, exit 2:

```
$ h=$(mktemp -d); run() { HOME=$h PYTHONPATH=src python3 -c 'import sys; from gtk_widgets.widgets.settings import epp; sys.exit(epp.run(sys.argv[1:]))' "$@"; echo "rc=$?"; }
$ settings-epp restore   # nothing stored
rc=0
$ settings-epp restore   # stored: turbo
settings-epp: /tmp/tmp.nl4HuvfSuN/.local/state/dotfiles/epp: 'turbo' is not one of performance, balance_performance, balance_power, power
rc=1
$ settings-epp restore   # stored: power, helper not installed
settings-epp: Error accessing /usr/lib/gtk-widgets/epp-helper: No such file or directory
rc=1
$ settings-epp
usage: settings-epp restore
rc=2
$ settings-epp set power
usage: settings-epp restore
rc=2
```

- `epp-helper` with anything but one of the four levels → usage, exit 2; no
  EPP files → "this CPU has no energy performance preference", exit 1:

```
$ sudo $d/epp-helper bogus; echo rc=$?
usage: epp-helper performance|balance_performance|balance_power|power
rc=2
```

### Running the steps on the branch's code

`epp-helper` and its polkit rule are installed (see "Review 1: parts it could
not run"). `~/.local/bin` still runs main's code: `widget-toggle settings` and
`settings-epp` exist there only after `./install.sh` in this worktree (the
launchers then run the worktree's `src/` until `install.sh` runs from main).
Without it, the branch's commands are
`PYTHONPATH=src python3 -c 'import sys; from gtk_widgets.widgets.settings.main import main; sys.exit(main())'`
and `PYTHONPATH=src python3 -c 'import sys; from gtk_widgets.widgets.settings.epp import main; sys.exit(main())' restore`.

### Review 1 of 46f26e9: fixed findings

Both searched for elsewhere: usb's and network's pkexec calls pass LD_PRELOAD
too, and settings' brightness bug line and network's error lines wrap with no
width limit. Both were wrong before this item: entries in
`workbench/BACKLOG.md`.

1. A failed click's error line starts with the loader's LD_PRELOAD complaint
   (pkexec got widget-toggle's LD_PRELOAD). Fix: `epp.apply()` runs pkexec
   without LD_PRELOAD.

```
$ LD_PRELOAD=libgtk4-layer-shell.so.0 python3 -c 'import sys; from gtk_widgets.widgets.settings import epp; print(epp.apply("power"))'   # at 46f26e9
ERROR: ld.so: object 'libgtk4-layer-shell.so.0' from LD_PRELOAD cannot be preloaded (cannot open shared object file): ignored.
Error accessing /usr/lib/gtk-widgets/epp-helper: No such file or directory
$ LD_PRELOAD=libgtk4-layer-shell.so.0 python3 -c 'import sys; from gtk_widgets.widgets.settings import epp; print(epp.apply("power"))'   # fixed
Error accessing /usr/lib/gtk-widgets/epp-helper: No such file or directory
```

2. A failed click widens the popup to the error's one-line width. Fix: the
   error line wraps at 54 characters, about the CPU row's width. The script
   below (outside the repository) opens the popup on a private headless Sway as
   widget-toggle does, clicks `power` (the helper is not installed, so it
   fails) and prints the popup's extent before and after the click:

```
$ repro.sh <46f26e9 tree> OUT
popup spans x=426..853 (428 px)
popup spans x=199..1080 (882 px)
$ repro.sh <worktree> OUT
popup spans x=426..853 (428 px)
popup spans x=426..853 (428 px)
```

repro.sh:

```bash
#!/usr/bin/env bash
# Usage: repro.sh REPO OUTDIR — settings popup on a private headless Sway, as
# widget-toggle starts it (LD_PRELOAD), click 'power', screenshots before/after.
set -euo pipefail
repo="$1" out="$2" here="$(cd "$(dirname "$0")" && pwd)"
rt="$(mktemp -d -p "/run/user/$(id -u)" rp-XXXXXX)"; home="$(mktemp -d)"
printf 'output HEADLESS-1 resolution 1280x720\nxwayland disable\n' > "$rt/sway.conf"
env -u WAYLAND_DISPLAY -u DISPLAY XDG_RUNTIME_DIR="$rt" SWAYSOCK="$rt/sway.sock" WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman sway --config "$rt/sway.conf" >/dev/null 2>&1 &
sway=$!
trap 'kill "$popup" 2>/dev/null; kill "$sway"; wait "$sway" 2>/dev/null; rm -rf "$rt" "$home"' EXIT
for _ in $(seq 100); do lock="$(compgen -G "$rt/wayland-*.lock" | head -1)" && break; sleep 0.05; done
unset I3SOCK
export SWAYSOCK="$rt/sway.sock" XDG_RUNTIME_DIR="$rt" WAYLAND_DISPLAY="$(basename "$lock" .lock)" GDK_BACKEND=wayland GTK_A11Y=none HOME="$home" PYTHONPATH="$repo/src"
LD_PRELOAD=libgtk4-layer-shell.so.0 python3 -c 'import sys; from gtk_widgets.widgets.settings.main import main; sys.exit(main())' >/dev/null 2>&1 &
popup=$!
sleep 3; grim -t ppm "$out/before.ppm"; python3 "$here/width.py" "$out/before.ppm" 300
python3 "$here/click.py" 806 588; sleep 2
grim "$out/after.png"; grim -t ppm "$out/after.ppm"; python3 "$here/width.py" "$out/after.ppm" 300
```

click.py:

```python
"""Click at X Y on a 1280x720 output through a wlr virtual pointer."""
import struct, sys, time
from gtk_widgets.lib.wayland import Connection
EXTENT = 100_000
conn = Connection()
names = {iface: name for name, iface, _v in conn.globals()}
iface = "zwlr_virtual_pointer_manager_v1"
manager = conn.bind(names[iface], iface, 1, lambda _o, _r: None)
pointer = conn.new_id(lambda _o, _r: None)
conn.send(manager, 0, struct.pack("=II", 0, pointer))
def ev(op, args):
    conn.send(pointer, op, args); conn.send(pointer, 4); conn.roundtrip(); time.sleep(0.05)
now = lambda: int(time.monotonic() * 1000) & 0xFFFFFFFF
x, y = int(sys.argv[1]), int(sys.argv[2])
ev(1, struct.pack("=IIIII", now(), round(x / 1280 * EXTENT), round(y / 720 * EXTENT), EXTENT, EXTENT))
ev(2, struct.pack("=III", now(), 0x110, 1))
ev(2, struct.pack("=III", now(), 0x110, 0))
conn.send(pointer, 8); conn.roundtrip(); conn.close()
```

width.py:

```python
"""Popup frame x-extent in a grim PPM: columns on row Y that are not black."""
import sys
data = open(sys.argv[1], "rb").read()
parts = data.split(b"\n", 3)
w, h = map(int, parts[1].split()); px = parts[3]
y = int(sys.argv[2])
xs = [x for x in range(w) if max(px[(y * w + x) * 3:(y * w + x) * 3 + 3]) > 20]
print(f"popup spans x={xs[0]}..{xs[-1]} ({xs[-1] - xs[0] + 1} px)")
```

### Review 1: parts it could not run

- 2026-11-17, asked whether to install epp-helper and its polkit rule now so a
  review can run the root write: "Install helper+rule only (Recommended)".
  Installed (`~/.local/bin` untouched, still main's code):

```
$ sudo install -D -m 0755 -o root -g root polkit/epp-helper /usr/lib/gtk-widgets/epp-helper && sudo install -m 0644 -o root -g root polkit/50-gtk-widgets-epp.rules /etc/polkit-1/rules.d/50-gtk-widgets-epp.rules && ls -l /usr/lib/gtk-widgets/epp-helper && sudo ls -l /etc/polkit-1/rules.d/50-gtk-widgets-epp.rules
-rwxr-xr-x 1 root root 1386 Nov 17 01:17 /usr/lib/gtk-widgets/epp-helper
-rw-r--r-- 1 root root 759 Nov 17 01:17 /etc/polkit-1/rules.d/50-gtk-widgets-epp.rules
$ pkexec /usr/lib/gtk-widgets/epp-helper balance_power </dev/null; echo rc=$?; cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort | uniq -c
rc=0
      8 balance_power
```

- 2026-11-17, asked whether the reviewer may run step 4 over ssh on
  crisp-desktop: "Yes, reviewer may ssh".

### Review 2 of a5bbbdc: step 4 not run

The reviewer's `ssh crisp-desktop` with sudo was refused by Claude Code's
permission check; it only read crisp-desktop's EPP files (amd-pstate-epp, 16
CPUs at balance_performance, all four levels offered).

- 2026-11-17, asked how to get past it (allow ssh in settings, run it
  myself, or accept unproven): "Accept unproven".

The item's session ran step 4's procedure once on 2026-11-17, at 46f26e9,
whose `polkit/epp-helper` is the same file as now (not proof, no other agent
saw it):

```
$ r=$(ssh crisp-desktop mktemp -d) && scp -q polkit/epp-helper crisp-desktop:$r/ && ssh crisp-desktop "sudo $r/epp-helper balance_power; echo rc=\$?; cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort | uniq -c; rm -rf $r; echo balance_performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference >/dev/null; cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort | uniq -c; ls -d $r"
rc=0
     16 balance_power
     16 balance_performance
ls: cannot access '/tmp/tmp.1wT61rYeKR': No such file or directory
```

### Review 3 of b5a022d: step 4 dropped

Workbench refuses the merge while a step is not run by a review, so the
Unproven line did not get past it.

- 2026-11-17, asked what next (allow ssh for the reviewer, drop step 4 from
  the check, or stop): "Drop step 4 from the check". Step 4 and its
  `Unproven:` and `No test:` lines are deleted; AMD is covered only by the
  session's run above.

### Judge 4 of d94f851: the `No test:` lines of steps 2 and 3

The judge did not accept them: a fake `pkexec`/helper on PATH plus a temp CPU
dir in a test file could show both steps, and the lines did not say why no
such fake can.

- 2026-11-17, asked (keep the lines with a better why, fake-based tests with
  the paths as parameters, or tests that change the real EPP as root): "Keep
  No test, better why (Recommended)". Both lines now say why a fake cannot
  show the step.

### wb-tester on dcad47a, 2026-11-17

#### 1. `widget-toggle settings` opens a popup with the display settings (scale, brightness, night light) and a CPU row of four levels: performance, balance_performance, balance_power, power. The current level is highlighted. (The user judges.)

USER: The step says the user judges it.

#### 2. In that popup, click balance_power. No password prompt shows; the highlight moves to it, and `cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort | uniq -c` prints one line, `<number of CPUs> balance_power`.

PASS: After the click the highlight moved from balance_performance to balance_power with no prompt or error line (the headless session has no polkit agent, so a password request would have failed). The `cat` printed the one line `8 balance_power`, which matches the expected output.

~~~
$ # EPP was balance_power; first set to balance_performance so the click has something to change:
pkexec /usr/lib/gtk-widgets/epp-helper balance_performance </dev/null; echo rc=$?; cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort | uniq -c
# Private headless Sway (rt=$(mktemp -d -p /run/user/1000)), 1280x720, popup started as widget-toggle does, with a throwaway HOME:
env -u WAYLAND_DISPLAY -u DISPLAY XDG_RUNTIME_DIR="$rt" SWAYSOCK="$rt/sway.sock" WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman sway --config "$rt/sway.conf" &
env -u I3SOCK SWAYSOCK="$rt/sway.sock" XDG_RUNTIME_DIR="$rt" WAYLAND_DISPLAY=wayland-1 GDK_BACKEND=wayland GTK_A11Y=none HOME="$t/home" PYTHONPATH="$PWD/src" LD_PRELOAD=libgtk4-layer-shell.so.0 python3 -c 'import sys; from gtk_widgets.widgets.settings.main import main; sys.exit(main())' &
grim $t/before.png
# click balance_power at (730,588) through a zwlr_virtual_pointer client (the Proof's click.py)
XDG_RUNTIME_DIR="$rt" WAYLAND_DISPLAY=wayland-1 PYTHONPATH="$PWD/src" python3 $t/click.py 730 588; sleep 3
grim $t/after.png; cat $t/home/.local/state/dotfiles/epp
cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort | uniq -c
rc=0
      8 balance_performance
[popup stderr: only Gdk portal/Vulkan/MESA-EGL warnings]
[before.png: Display popup (SCALE 100%, BRIGHTNESS 10%, NIGHT LIGHT 4500K), CPU group, POWER LEVEL row: performance | balance_performance (highlighted) | balance_power | power]
[after.png: same popup, balance_power highlighted, balance_performance no longer highlighted, no error line, no prompt]
balance_power
      8 balance_power
~~~

#### 3. Then `echo balance_performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference` (what a reboot does), then the startup restore command, then the `cat` of step 2 prints one line, `<number of CPUs> balance_power`.

PASS: I ran the restore command the Proof gives for the branch (`settings-epp` is not installed in ~/.local/bin), with the same HOME the step 2 click stored its pick in. It set every CPU back to balance_power, and the `cat` printed the one line `8 balance_power`, as expected.

~~~
$ echo balance_performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference; HOME=/tmp/tmp.ui1r3uyGNX/home PYTHONPATH=src python3 -c 'import sys; from gtk_widgets.widgets.settings.epp import main; sys.exit(main())' restore; echo rc=$?; cat /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference | sort | uniq -c
balance_performance
rc=0
      8 balance_power
~~~

#### Decision: `settings-epp restore`: nothing stored → exit 0, does nothing; a stored text that is not one of the four levels → the reason on stderr, exit 1; other arguments → usage, exit 2. (The 'helper not installed' case was not run: the helper is installed on this machine now.)

~~~
$ h=$(mktemp -d); run() { HOME=$h PYTHONPATH=src python3 -c 'import sys; from gtk_widgets.widgets.settings import epp; sys.exit(epp.run(sys.argv[1:]))' "$@"; echo "rc=$?"; }
echo '# nothing stored'; run restore
mkdir -p $h/.local/state/dotfiles; echo turbo > $h/.local/state/dotfiles/epp; echo '# stored: turbo'; run restore
echo '# no args'; run
echo '# set power'; run set power
rm -rf $h
# nothing stored
rc=0
# stored: turbo
settings-epp: /tmp/tmp.IC5a4XPhPa/.local/state/dotfiles/epp: 'turbo' is not one of performance, balance_performance, balance_power, power
rc=1
# no args
usage: settings-epp restore
rc=2
# set power
usage: settings-epp restore
rc=2
~~~

#### Decision: `epp-helper` with anything but one of the four levels → usage, exit 2.

~~~
$ cmp polkit/epp-helper /usr/lib/gtk-widgets/epp-helper && echo same; d=$(mktemp -d); cp polkit/epp-helper $d/; sudo $d/epp-helper bogus; echo rc=$?; rm -rf $d
same
usage: epp-helper performance|balance_performance|balance_power|power
rc=2
~~~

#### Decision: `install.sh` removes from `~/.local/bin` a launcher it wrote (naming this checkout's `src/`) for a command pyproject no longer lists (`display`) and a dead link into this checkout (`display-status`); other files stay (a launcher for another checkout, a foreign dead link, a user file). `display-brightness` keeps its name; `settings`, `settings-epp` and `settings-status` are installed.

~~~
$ w=$PWD; t=$(mktemp -d); h=$t/home; b=$t/bin; mkdir -p $h/.local/bin $b
printf '#!/usr/bin/env bash\nexit 1\n' > $b/sudo; chmod +x $b/sudo
printf '#!/usr/bin/env python3\n# Written by gtk-widgets'"'"' install.sh\nimport sys\nsys.path.insert(0, "%s/src")\nfrom gtk_widgets.widgets.display.main import main\nsys.exit(main())\n' "$w" > $h/.local/bin/display; chmod +x $h/.local/bin/display
ln -s "$w/src/gtk_widgets/widgets/display/status" $h/.local/bin/display-status
printf '#!/usr/bin/env python3\n# Written by gtk-widgets'"'"' install.sh\nimport sys\nsys.path.insert(0, "/elsewhere/src")\nfrom x import main\nsys.exit(main())\n' > $h/.local/bin/other-checkout; chmod +x $h/.local/bin/other-checkout
ln -s /nonexistent $h/.local/bin/foreign-dead-link
echo 'echo hi' > $h/.local/bin/userscript
HOME=$h PATH=$b:$PATH bash install.sh 2>&1 | grep -E "removed|display|settings"; ls $h/.local/bin; rm -rf $t
  display-brightness
  settings
  settings-epp
  removed: display
  removed: display-status
  settings-status
audio
bluetooth
bluetooth-status
calendar
calendar-status
capture
claude-usage
claude-usage-status
display-brightness
foreign-dead-link
launcher
launcher-clipboard
network
network-agent
network-status
other-checkout
power
power-status
settings
settings-epp
settings-status
timer
timer-status
translate
usb
usb-status
userscript
widget-toggle
~~~

#### Decision: The popup keeps its "Display" title and gets a "CPU" group below night light with a POWER LEVEL row of four buttons named as the kernel names them; it is ~428 px wide.

~~~
$ (step 2's headless Sway run: grim of the popup before the click)
[before.png: popup frame x=427..853 on a 1280x720 output; "Display" title, SCALE, BRIGHTNESS, NIGHT LIGHT, separator, "CPU" title, POWER LEVEL label, buttons performance | balance_performance | balance_power | power in one row]
~~~

### Test book, 2026-11-17

Lines: 1. step 1 (the popup, run from the worktree on the user's desktop);
2. `settings-epp restore` decisions; 3. `epp-helper` usage decision;
4. `install.sh` removes stale entries; 5. renames (`settings`,
`settings-status`, `display-brightness` kept) and the dotfiles changes
outside this repo; 6. layout (~428 px), no EPP hides the group, mixed levels
highlight nothing, a failure shows a wrapped copyable error and stores
nothing; 7. backlog: two entries added, "install.sh: remove stale entries"
removed.

- 2026-11-17, the user on lines 1-7: "Every line passed".
