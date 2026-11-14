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
