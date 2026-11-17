# b-bluetooth-an-action-s-result-is-lost-when-the-adap-261114-2300 — bluetooth: an action's result is lost when the adapter is off

## Why

If Bluetooth is powered off while connect, pair, remove or disconnect runs, the
popup's redraw at its end shows only "Bluetooth is powered off" and has no
status line: the result ("Connected", "Connection failed", a bug line) is lost
and nobody sees it. Found in gap 5 of the py-gate move (types), 2026-11-14.

## Root cause

When an action ends, `_after_action()` rebuilds the popup and then writes the
result to `self._status`. Only the powered-on layout creates that label, so after
a redraw into the powered-off layout the write goes to the old label, which is
no longer in the popup.

## Check

1. The user judges it on screen. Open the Bluetooth popup. Click Connect on a
   paired device that is switched off or out of range (bluetoothctl tries for
   up to 10 s). Before the attempt ends, click the popup's power button to turn
   Bluetooth off. Expected: once the attempt ends, the popup shows "Bluetooth
   is powered off" and, below it, the result line "Connection failed".

## Proof

- Check agreed by the user on 2026-11-15 ("Agree").
- Step 1 before the change: not run yet. The user, 2026-11-15: "got no device to
  test it rn. lets do it later".
- Asked again on 2026-11-15; the user: "lets postpone that when I will have device to
  run".
