#!/usr/bin/env bash
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
FINDING='error|^[^ ]+:[0-9]+:|FAILED|DEP0|BROKEN'

conf_count() {
  local line k v=""
  if [ -f .claude/workshop.conf ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      line="${line#"${line%%[![:space:]]*}"}"; line="${line%"${line##*[![:space:]]}"}"
      case "$line" in '#'*) continue ;; *=*) ;; *) continue ;; esac
      k=${line%%=*}; k="${k%"${k##*[![:space:]]}"}"
      [ "$k" = "$1" ] || continue
      v=${line#*=}; v="${v#"${v%%[![:space:]]*}"}"
    done < .claude/workshop.conf
  fi
  if [[ "$v" =~ ^[1-9][0-9]{0,8}$ ]]; then echo "$v"; else echo "$2"; fi
}
IN=$(cat)
OUT=$(bash py-gate/scripts/gate.sh --local 2>&1) && exit 0
CAP=$(conf_count py-gate.repeat_cap 3)
MAX_LINES=$(conf_count py-gate.output_lines 80)

SID=$(printf '%s' "$IN" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
SAME=1
if [ -n "$SID" ]; then
  MARK="${TMPDIR:-/tmp}/py-gate-stop-$SID"
  # A runner that shuffles the failures (pytest-randomly) or ends its summary
  # in a run time (pytest's) must not make the same failures look new, nor
  # pytest's numbered temp folder (pytest-N) or an object's address.
  FINDINGS=$(printf '%s\n' "$OUT" | grep -iE "$FINDING" | sed -E 's/ in [0-9.]+s( \([0-9:]+\))?$//; s/pytest-[0-9]+/pytest-N/g; s/0x[0-9a-fA-F]+/0x/g' | sort || true)
  HASH=$(printf '%s' "${FINDINGS:-$OUT}" | sha256sum | cut -c1-16)
  read -r LAST N 2>/dev/null < "$MARK" || { LAST=""; N=0; }
  [ "$HASH" = "$LAST" ] && SAME=$((N + 1))
  printf '%s %s\n' "$HASH" "$SAME" > "$MARK"
fi
[ "$SAME" -le "$CAP" ] || exit 0

LINES=$(printf '%s\n' "$OUT" | wc -l)
if [ "$LINES" -gt "$MAX_LINES" ]; then
  OUT=$(printf '%s\n' "$OUT" | head -n "$MAX_LINES"; echo "… $((LINES - MAX_LINES)) more lines; run bash py-gate/scripts/gate.sh --local for all of it")
fi
if [ "$SAME" -eq "$CAP" ]; then
  printf 'The gate failed the same way %s times. Do not try again. Ask the user what to do, through the question prompt of your environment. Quote this line to the user:\n%s\nThe next stop is allowed.\n' \
    "$CAP" "$(printf '%s\n' "$OUT" | grep -m1 -E "$FINDING" | cut -c1-120)" >&2
fi
printf '%s\n' "$OUT" >&2
exit 2
