#!/usr/bin/env bash
# Inside probe.sh's scope: throwaway HOME, private XDG_RUNTIME_DIR and session bus.
# Usage: inner.sh REPO OUT WORK
set -euo pipefail

repo="$1" out="$2" work="$3"
report="${out}/report.txt"
logs="${out}/logs"
mkdir -p "${HOME}" "${logs}" "${work}/bin" "${work}/shots"
: > "${report}"
say() { printf '%s\n' "$*" >> "${report}"; }

# install.sh must not need root here; a sudo it calls fails and is reported
printf '#!/usr/bin/env bash\necho "SUDO CALLED: $*" >&2\nexit 1\n' > "${work}/bin/sudo"
chmod +x "${work}/bin/sudo"
export PATH="${HOME}/.local/bin:${work}/bin:${PATH}"

say "## install.sh"
if bash "${repo}/install.sh" > "${logs}/install.log" 2>&1; then say "install.sh: exit 0"; else say "install.sh: FAILED (see logs/install.log)"; fi
if grep -q "SUDO CALLED" "${logs}/install.log"; then say "install.sh: called sudo"; fi
for f in "${HOME}"/.local/bin/*; do
  if [[ -x "${f}" ]]; then say "bin: $(basename "${f}") executable"; else say "bin: $(basename "${f}") NOT EXECUTABLE"; fi
done

# Headless Sway
cat > "${work}/sway.conf" <<EOF
output HEADLESS-1 resolution 1280x720
xwayland disable
EOF
WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman \
  SWAYSOCK="${XDG_RUNTIME_DIR}/sway.sock" sway --config "${work}/sway.conf" > "${logs}/sway.log" 2>&1 &
sway_pid=$!
trap 'kill "${sway_pid}" 2>/dev/null || true' EXIT
lock=""
for _ in $(seq 100); do
  lock="$(compgen -G "${XDG_RUNTIME_DIR}/wayland-*.lock" | head -1)" && break
  sleep 0.05
done
[[ -n "${lock}" ]] || { say "sway: no socket"; exit 1; }
WAYLAND_DISPLAY="$(basename "${lock}" .lock)"
export WAYLAND_DISPLAY
export SWAYSOCK="${XDG_RUNTIME_DIR}/sway.sock" GDK_BACKEND=wayland GTK_A11Y=none GDK_DEBUG=no-portals
sleep 0.5

# A log with a Python traceback or an import failure counts as broken.
clean() { ! grep -qE "Traceback|ModuleNotFoundError|ImportError|No module named" "$1"; }

# Runs CMD for SECS; ok when it is still running then (killed by timeout: 124)
# or exits with one of the allowed codes, with no traceback.
run_for() {
  local name="$1" secs="$2" allowed="$3" rc=0
  shift 3
  local log="${logs}/${name}.log"
  timeout -s TERM "${secs}" "$@" > "${log}" 2>&1 < /dev/null || rc=$?
  if [[ " ${allowed} " == *" ${rc} "* ]] && clean "${log}"; then
    say "run ${name}: ok (exit ${rc})"
  else
    say "run ${name}: FAILED (exit ${rc}, see logs/${name}.log)"
  fi
}

say "## popups: direct run (4 s), screenshot, then widget-toggle on/off"
for w in audio bluetooth calendar claude-usage display network power timer translate usb; do
  log="${logs}/${w}.log"
  timeout -s TERM 4 "${HOME}/.local/bin/${w}" > "${log}" 2>&1 < /dev/null &
  tpid=$!
  sleep 3
  grim "${out}/${w}.png" 2>/dev/null || true
  rc=0
  wait "${tpid}" || rc=$?
  if [[ "${rc}" == 124 ]] && clean "${log}"; then say "run ${w}: ok (alive at 4 s)"; else say "run ${w}: FAILED (exit ${rc}, see logs/${w}.log)"; fi

  pidfile="${XDG_RUNTIME_DIR}/gtk-widgets-${w}-toggle.pid"
  widget-toggle "${w}"
  sleep 3
  pid="$(cat "${pidfile}" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    widget-toggle "${w}"
    sleep 2
    if kill -0 "${pid}" 2>/dev/null; then
      say "toggle ${w}: on ok, off FAILED"
      kill "${pid}" 2>/dev/null || true
    else
      say "toggle ${w}: on/off ok"
    fi
  else
    say "toggle ${w}: on FAILED (not running at 3 s)"
  fi
done

say "## status scripts (first line must be JSON)"
for s in bluetooth calendar claude-usage display network power timer usb; do
  log="${logs}/${s}-status.log"
  line="$(timeout 6 "${s}-status" 2> "${log}" | head -1 || true)"
  if python3 -c 'import json,sys; json.loads(sys.argv[1])' "${line}" 2>/dev/null && clean "${log}"; then
    say "status ${s}-status: ok"
  else
    say "status ${s}-status: FAILED (line: ${line})"
  fi
done
run_for claude-usage-status-refresh 20 "0" claude-usage-status --refresh-cache
run_for claude-usage-status-json 20 "0" claude-usage-status --json

say "## other commands"
run_for display-brightness-get 20 "0 1" display-brightness get
run_for launcher-clipboard 10 "0" launcher-clipboard
run_for network-agent 3 "124" network-agent
run_for launcher-dmenu 3 "124" bash -c 'printf "alpha\nbeta\n" | launcher --dmenu --prompt probe'
run_for capture-region 4 "124" capture region --dir "${work}/shots"
run_for capture-gif-cancel 5 "1" capture gif --cancel

# launcher: a toggle starts the resident instance, a second one hides it
rc=0
launcher > "${logs}/launcher-toggle.log" 2>&1 < /dev/null || rc=$?
sleep 3
grim "${out}/launcher.png" 2>/dev/null || true
if [[ "${rc}" == 0 && -S "${XDG_RUNTIME_DIR}/gtk-widgets-launcher.sock" ]]; then
  launcher >> "${logs}/launcher-toggle.log" 2>&1 < /dev/null || rc=$?
  if [[ "${rc}" == 0 ]] && clean "${logs}/launcher-toggle.log"; then say "launcher toggle: ok"; else say "launcher toggle: FAILED (second toggle exit ${rc})"; fi
else
  say "launcher toggle: FAILED (first toggle exit ${rc}, or no instance socket)"
fi
say "## done"
