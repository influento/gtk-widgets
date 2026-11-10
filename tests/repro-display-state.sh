#!/usr/bin/env bash
# Guards for the display popup's state files (widgets/display/main.py).
# The popup keeps the sway scale and the night light temperature in
# ~/.local/state/dotfiles/{scale.conf,temperature}: sway includes scale.conf,
# dotfiles' wlsunset.sh reads temperature at sway startup.
#
# Each case runs the real apply_scale/apply_temperature in a throwaway HOME,
# with swaymsg, pkill and wlsunset stubbed in PATH, so the live session is
# never touched. Exit 1 if any case fails.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT

mkdir -p "${work}/bin"
for cmd in swaymsg pkill wlsunset; do
  printf '#!/usr/bin/env bash\nexit 0\n' > "${work}/bin/${cmd}"
  chmod +x "${work}/bin/${cmd}"
done

# Lays out a HOME like the workstation's: ~/.config/sway and
# ~/.config/wlsunset are symlinks into a dotfiles checkout.
make_linked_home() {
  local home="$1"
  mkdir -p "${home}/.config" "${home}/dotfiles/sway" "${home}/dotfiles/wlsunset"
  ln -s "${home}/dotfiles/sway" "${home}/.config/sway"
  ln -s "${home}/dotfiles/wlsunset" "${home}/.config/wlsunset"
}

# A file, not stdin: lib/widget_base.py re-execs Python (LD_PRELOAD), and the
# re-exec would find stdin already read
cat > "${work}/case.py" <<'EOF'
import os, resource, sys

sys.path.insert(0, sys.argv[1])
import main  # noqa: E402

case = sys.argv[2]
home = os.environ["HOME"]
state = os.path.join(home, ".local", "state", "dotfiles")


def read(path):
    with open(path) as f:
        return f.read()


def fail(msg):
    print(f"  {msg}")
    sys.exit(1)


def files_under(path):
    return sorted(os.path.join(d, f) for d, _, fs in os.walk(path) for f in fs)


if case == "state-path":
    main.apply_scale(1.3)
    main.apply_temperature(3700)
    for name, want in [("scale.conf", "output * scale 1.3\n"),
                       ("temperature", "3700\n")]:
        path = os.path.join(state, name)
        if not os.path.exists(path):
            fail(f"{path} not written")
        if read(path) != want:
            fail(f"{path} holds {read(path)!r}, want {want!r}")
    if main.get_temperature() != 3700:
        fail(f"get_temperature() = {main.get_temperature()}, want 3700")
    stray = files_under(os.path.join(home, "dotfiles"))
    if stray:
        fail(f"state written into the dotfiles checkout: {stray}")

elif case == "missing-dir":
    # A fresh HOME: neither ~/.config/sway nor ~/.local/state/dotfiles exists
    try:
        main.apply_scale(1.3)
    except OSError as e:
        fail(f"apply_scale raised {type(e).__name__}: {e}")
    path = os.path.join(state, "scale.conf")
    if not os.path.exists(path):
        fail(f"{path} not written")

elif case == "interrupted-write":
    # Every state file the popup could write holds an old value; then each
    # write fails (file size limit 0, as on a full disk). Readers must still
    # find the old value whole, never an empty file.
    seeded = {
        os.path.join(home, ".config", "sway", "scale.conf"): "output * scale 2.0\n",
        os.path.join(home, ".config", "wlsunset", "temperature"): "3600\n",
        os.path.join(state, "scale.conf"): "output * scale 2.0\n",
        os.path.join(state, "temperature"): "3600\n",
    }
    os.makedirs(state, exist_ok=True)
    for path, text in seeded.items():
        with open(path, "w") as f:
            f.write(text)
    errors = []
    for call in (lambda: main.apply_scale(1.3),
                 lambda: main.apply_temperature(3700)):
        # The limit goes back up before anything prints: stdout may be a file
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, resource.RLIM_INFINITY))
        try:
            call()
        except OSError:
            pass
        finally:
            resource.setrlimit(resource.RLIMIT_FSIZE,
                               (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
    for path, text in seeded.items():
        if read(path) != text:
            errors.append(f"{path} holds {read(path)!r}, want {text!r}")
    leftovers = [p for p in files_under(state) if p not in seeded]
    if leftovers:
        errors.append(f"temp files left behind: {leftovers}")
    if errors:
        fail("; ".join(errors))
EOF

run_case() {
  local name="$1" home="$2"
  if HOME="${home}" PATH="${work}/bin:${PATH}" \
    env -u WAYLAND_DISPLAY -u DISPLAY \
    python3 "${work}/case.py" "${repo}/widgets/display" "${name}"; then
    echo "PASS ${name}"
  else
    echo "FAIL ${name}"
    return 1
  fi
}

status=0

make_linked_home "${work}/home-state-path"
run_case state-path "${work}/home-state-path" || status=1

mkdir -p "${work}/home-missing-dir"
run_case missing-dir "${work}/home-missing-dir" || status=1

make_linked_home "${work}/home-interrupted"
run_case interrupted-write "${work}/home-interrupted" || status=1

exit "${status}"
