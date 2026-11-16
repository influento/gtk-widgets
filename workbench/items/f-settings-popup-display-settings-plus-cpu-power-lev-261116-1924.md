# f-settings-popup-display-settings-plus-cpu-power-lev-261116-1924 — Settings popup: display settings plus CPU power level (EPP) switching

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
4. On crisp-desktop (AMD), nothing installed there: the item's root helper,
   copied into a `mktemp -d` directory and run over ssh with sudo for
   balance_power, makes the `cat` of step 2 print one line,
   `16 balance_power`. The copy is deleted and EPP set back to
   balance_performance afterwards.

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
