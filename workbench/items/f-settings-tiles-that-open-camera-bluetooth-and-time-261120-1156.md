# f-settings-tiles-that-open-camera-bluetooth-and-time-261120-1156 — Settings: tiles that open Camera, Bluetooth and Timer

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
