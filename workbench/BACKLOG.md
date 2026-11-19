- **install.sh: no sudo when the root-installed files are unchanged.** The
  check compares the polkit rules with `/etc/polkit-1/rules.d`, which is
  root:polkitd 0750, so the compare always fails and sudo runs every time. The
  sudo step writes `/usr/lib/gtk-widgets/installed.sha256` (0644), the hashes
  of each file it installs (helpers, rules, unit); the next run skips sudo when
  the repo copies hash the same. The user's pick (2026-11-14). An item once the
  gate passes.
- **bluetooth: an action's result is lost when the adapter is off.** If
  Bluetooth is powered off while connect, pair, remove or disconnect runs, the
  redraw at its end shows only "Bluetooth is powered off" and has no status
  line: the result ("Connected", "Pairing failed", a bug line) goes to the old,
  removed label and nobody sees it. Found in gap 5 (types), left as it was
  (2026-11-14).
- **translate: a closed popup leaves its claude request running.** Closed by
  the hotkey (`widget-toggle`'s SIGTERM) or by Esc while it works, ezpick's
  `claude -p` request keeps running to its end (up to its 30 s timeout), its
  parent now pid 1, and spends tokens on an answer nobody sees. Seen on a
  headless Sway with a fake `claude`; left out of
  b-a-popup-closed-by-its-hotkey-leaves-its-child-proc-261116-1503 by the
  user, "since its unfinished widget" (2026-11-16).
- **usb, network: pkexec errors start with a loader line.** widget-toggle
  starts popups with `LD_PRELOAD=libgtk4-layer-shell.so.0`; usb's `_helper()`
  and network's `run_helper()` pass it on to the setuid pkexec, whose loader
  prints "ERROR: ld.so: object 'libgtk4-layer-shell.so.0' from LD_PRELOAD
  cannot be preloaded ..." on the stderr that becomes the error line. Found
  in review of f-settings-popup-display-settings-plus-cpu-power-lev-261116-1924
  for its own pkexec call; usb and network seen in the code only (2026-11-17).
- **Wrapped error lines with no width limit widen their popup.** A wrapping
  label with no max width chars asks for its whole one-line width: settings'
  brightness bug line (`_show_bug`), network's form error lines
  (`ui.error_label()`) and its `_inet_msg`. Found in review of
  f-settings-popup-display-settings-plus-cpu-power-lev-261116-1924 for its EPP
  error line (popup 428 px to 882 px); the others seen in the code only
  (2026-11-17).
- **audio: voice processing tunes itself to the room.** A guided self-test
  runs cases on the user's setup, e.g. room noise, typing, speech, speech over
  sound from the speakers, and measures each stage (raw mic, after the echo
  canceller, after the noise filter). From that it sets the most adaptive
  settings. Where cases trade off (e.g. typing silenced vs soft speech kept, or
  a quiet echo vs a voice ducked while the speakers play), it shows the options
  and the user picks one. UI/UX still open. Why: on 2026-11-19, a video playing
  from the speakers made the user barely heard. The echo canceller cut about
  half of the speech over the video (raw mic: voice −42 dBFS, video −48), and
  DeepFilterNet cut a further ~8 dB. The user turned processing off for a call.
  Asked for by the user (2026-11-19). Limits seen so far: the user must speak
  live in a guided take of 1–2 minutes, because speech played from the speakers
  is echo. The noise filters (LADSPA) can be tried offline on one take at many
  settings. PipeWire's WebRTC echo canceller has no strength setting, so for
  that stage the test can only advise (speaker volume, mic distance and
  direction, headphones). Results go stale when the setup changes. Level scores
  miss how the voice sounds, so the user picks by ear. Start with a spike:
  does offline filtering match the live filter, which scores match the user's
  ear, and how short can the guided take be.
