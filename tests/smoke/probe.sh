#!/usr/bin/env bash
# Runs install.sh into a throwaway HOME and every installed command on a
# private headless Sway with a private session bus. Writes report.txt and a
# screenshot per popup into OUT. Never touches the user's display or bin.
# The commands still see the system bus (NetworkManager: network-agent is a
# secret agent for 3 s), the PulseAudio server and the displays' DDC.
# A change keeps every command working when the report matches the one from
# a checkout before it (`git worktree add`, or `git archive HEAD | tar -x`).
# Usage: probe.sh REPO OUT
set -euo pipefail

repo="$(cd "$1" && pwd)"
out="$2"
mkdir -p "${out}"
out="$(cd "${out}" && pwd)"
here="$(cd "$(dirname "$0")" && pwd)"

work="$(mktemp -d)"
runtime="$(mktemp -d -p "/run/user/$(id -u)" gwp-XXXXXX)"
chmod 700 "${runtime}"
unit="gtkw-probe-$$"

cleanup() {
  systemctl --user stop "${unit}.scope" 2>/dev/null || true
  rm -rf "${work}" "${runtime}"
}
trap cleanup EXIT

# Everything the probe starts lives in this scope; stopping it kills them all.
systemd-run --user --scope --quiet --unit="${unit}" \
  env -i \
  PATH="/usr/local/bin:/usr/bin:/bin" \
  HOME="${work}/home" \
  XDG_RUNTIME_DIR="${runtime}" \
  PULSE_SERVER="unix:/run/user/$(id -u)/pulse/native" \
  LANG="${LANG:-C.UTF-8}" \
  dbus-run-session -- bash "${here}/inner.sh" "${repo}" "${out}" "${work}" 2> "${out}/session.log"
