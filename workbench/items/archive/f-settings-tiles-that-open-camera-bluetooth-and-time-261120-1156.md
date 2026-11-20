# f-settings-tiles-that-open-camera-bluetooth-and-time-261120-1156 — Settings: tiles that open Camera, Bluetooth and Timer

No review, tester run or test book: the user, 2026-11-20, chose to skip workbench for this item ("Yes, skip workbench") and to squash it onto main by hand.

## Why

The settings popup has only the display and CPU rows. The user uses the
webcam, bluetooth and timer widgets rarely and wants to reach them from
settings instead of the bar. The widgets stay independent: settings only
opens them and does not hold their code (option A of the design options,
https://claude.ai/artifact/4XKYnqcrBCkUeLvTQtpw46). The dotfiles session
removes their bar icons. That change is outside this repo.

## Check

1. `widget-toggle settings` opens the popup with the display and CPU rows as
   before, and below them a row of three tiles: Camera, Bluetooth, Timer.
   (The user judges.)
2. Click each tile in turn, opening settings again each time. Settings closes
   and the tile's widget opens in its place, the same as
   `widget-toggle webcam|bluetooth|timer` opens it. (The user judges.)
3. After the Bluetooth tile opened Bluetooth, `widget-toggle bluetooth` closes
   it. (The user judges.)

## Proof

### What the user said

- 2026-11-20, on the options: "I would pick A because I dont see real
  benefits for me from B while Id prefer C however it would mean more
  changes".
- 2026-11-20, on the tiles: Camera, Bluetooth, Timer.
- 2026-11-20, on a back button: "idk how about it just shows me a widget
  itself and that's it. I can pin it if I need to play around it".
- 2026-11-20, on hiding bar icons: "if its about waybar then we will remove
  those icons from there but its separate dotfiles related part".
- 2026-11-20, on the check: "Agree" (steps 1-3). Before the change all three
  fail: settings has no tiles.
- 2026-11-20, on the process: "Yes, skip workbench"; landing: "Squash onto main".

### Agent's run on a private headless Sway (2026-11-20)

Throwaway HOME with install.sh's launchers, a fake `bluetoothctl` (adapter
on, no devices) and a stand-in `webcam` launcher (the real one would open the
user's camera). `widget-toggle settings`, a virtual-pointer click on each tile,
then `widget-toggle <name>`. Settings showed the three tiles below the CPU row.
The first run found the click handler blocking: settings inherits
`WIDGET_TOGGLE_DETACHED=1` from its own widget-toggle, so the nested one ran in
the foreground; the child now gets an environment without it. Output after
the fix:

```
== webcam tile: settings pid 165815
settings: closed
webcam: open (pid 165893, bash /tmp/tmp.PylIqwOgJc/home/.local/bin/webcam )
webcam: closed by widget-toggle webcam
== bluetooth tile: settings pid 166052
settings: closed
bluetooth: open (pid 166236, python3 /tmp/tmp.PylIqwOgJc/home/.local/bin/bluetooth )
bluetooth: closed by widget-toggle bluetooth
== timer tile: settings pid 166450
settings: closed
timer: open (pid 166638, python3 /tmp/tmp.PylIqwOgJc/home/.local/bin/timer )
timer: closed by widget-toggle timer
```

`workbench/checks`: 65 passed.
