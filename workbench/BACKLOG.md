- **install.sh: remove stale entries in ~/.local/bin.** After the src/ move, all 23
  commands were left as dead links. install.sh removes an entry only if it is a
  symlink into this checkout or a launcher it wrote (it names this checkout's
  `src/`), and the entry is no longer a command in `pyproject.toml` or a status
  script. It never touches other files. Asked for by dotfiles; the user chose
  ownership over a manifest (2026-11-14). An item once the gate passes.
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
- **Saves through a fixed `.tmp` name can clobber each other.** `voice.py`
  (`_write`) and `timer/state.py` write `<file>.tmp` then rename it; two
  writers at once (the timer popup and `timer-status`, or a voice apply and
  the popup's flush) take each other's temp file. The mic lights now write a
  temp file of their own (`tempfile.mkstemp`). `lights.py` also repeats
  `voice.py`'s write and systemctl helpers: one shared copy would fix both.
  Found in the mic lights review, left for later (the user, 2026-11-18).
- **audio popup: pulse calls miss libpulse's `CallError`.** `popup.py` catches
  only `pulsectl.PulseError` around its command connection (`_call`,
  `_fetch`, writes); a call on a dropped context raises `CallError` instead
  (seen with `context_disconnect`). The mic lights' watcher catches both.
  Found in the mic lights review, left for later (the user, 2026-11-18).
