#!/usr/bin/env bash
# shellcheck disable=SC2329  # fmt, approved, deps, cycles and tests are called through run
# py-gate: lint, format, types, the gate's own rules, dependencies, import
# cycles, tests. Modes: none (the whole project), --local (what the Stop hook
# runs: format on the branch's changed files), --fix (ruff's fixes and the
# formatter, nothing else), --legacy (the files that fail lint, format, types
# or the gate's own rules, for install's py-gate-legacy.txt). Every tool runs
# even when another fails.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
# uv ignores an activated environment with a warning, and an absolute
# UV_PROJECT_ENVIRONMENT would share one between worktrees.
unset VIRTUAL_ENV UV_PROJECT_ENVIRONMENT
FAIL=0
MODE="${1:-}"
UV=(uv run --locked --exact --quiet)
# shellcheck source-path=SCRIPTDIR/../../../shared source=test-lock.sh
. py-gate/scripts/test-lock.sh

default_branch() {
  git symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null && return
  local b; for b in main master; do git show-ref -q --verify "refs/heads/$b" && { echo "$b"; return; }; done
  echo HEAD
}
run() { "$@" || FAIL=1; }
# A tool that prints a banner or a summary when it passes: its output only when it fails.
quiet() { local out; out=$("$@" 2>&1) && return; printf '%s\n' "$out"; return 1; }

mapfile -t EXCLUDE < <(python3 py-gate/conf.py exclude)
RUFF_X=(); [ ${#EXCLUDE[@]} -eq 0 ] || RUFF_X=(--extend-exclude "$(IFS=,; echo "${EXCLUDE[*]}")")
# Passed a --config, ruff stops reading requires-python and lints for an older
# Python: it then flags 3.14's lazy annotations (TC004) and misses UP040.
TARGET=$(python3 py-gate/conf.py target-version)
[ -z "$TARGET" ] || RUFF_X+=(--target-version "$TARGET")
# The files py-gate-legacy.txt lists failed the gate when it came into the
# project: no tool but pytest checks them until their line is deleted.
mapfile -t LEGACY < <(python3 py-gate/conf.py legacy)
[ ${#LEGACY[@]} -eq 0 ] || RUFF_X+=(--extend-exclude "$(IFS=,; echo "${LEGACY[*]}")")

if [ "$MODE" = "--fix" ]; then
  "${UV[@]}" ruff check --config ruff.toml --ignore-noqa --fix --quiet --force-exclude "${RUFF_X[@]}" .; c=$?
  "${UV[@]}" ruff format --config ruff.toml --quiet --force-exclude "${RUFF_X[@]}" .; f=$?
  exit $((c > f ? c : f))
fi

FILES=(.)
if [ "$MODE" = "--local" ]; then
  XPATH=()
  for g in "${EXCLUDE[@]}"; do XPATH+=(":(exclude,glob)$g"); done
  RANGE=$(git merge-base HEAD "$(default_branch)" 2>/dev/null || echo HEAD)
  # A deleted file is a change too: what imported it breaks. Only files that
  # exist get the format check.
  mapfile -t CHANGED < <({ git diff --relative --name-only --diff-filter=ACMRD "$RANGE" -- . "${XPATH[@]}"; git ls-files --others --exclude-standard -- . "${XPATH[@]}"; } | sort -u)
  FILES=()
  for f in "${CHANGED[@]}"; do [[ "$f" =~ \.pyi?$ && -e "$f" ]] && FILES+=("$f"); done
  if [ ${#FILES[@]} -eq 0 ]; then
    printf '%s\n' "${CHANGED[@]}" \
      | grep -qE '\.pyi?$|^(pyproject\.toml|uv\.lock|\.python-version|ruff\.toml|pyrightconfig\.json|pytest\.toml|py-gate/.*|py-gate-legacy\.txt|\.claude/workshop\.conf)$' \
      || { echo "no Python or config changes"; exit 0; }
    echo "== no changed Python files; project-wide checks only =="
  fi
fi

# The first uv run syncs the worktree's own .venv from its lock; one that
# fails stops the gate, since no tool after it would run.
quiet uv sync --locked --exact --quiet || { echo "uv sync --locked failed: uv.lock and pyproject.toml disagree. Run uv lock."; exit 1; }

mapfile -t PYRIGHT_PATHS < <(python3 py-gate/conf.py pyright-paths)
PYRIGHT=(basedpyright -p pyrightconfig.json --baselinefile py-gate/no-baseline.json)

if [ "$MODE" = "--legacy" ]; then
  {
    "${UV[@]}" ruff check --config ruff.toml --ignore-noqa --output-format concise --quiet --force-exclude "${RUFF_X[@]}" .
    "${UV[@]}" ruff format --config ruff.toml --check --output-format concise --quiet --force-exclude "${RUFF_X[@]}" .
    "${UV[@]}" python py-gate/check.py
  } 2>&1 | python3 py-gate/scripts/legacy.py paths > "${TMPDIR:-/tmp}/py-gate-legacy.$$"
  "${UV[@]}" "${PYRIGHT[@]}" --outputjson "${PYRIGHT_PATHS[@]}" | python3 py-gate/scripts/legacy.py paths >> "${TMPDIR:-/tmp}/py-gate-legacy.$$"
  "${UV[@]}" python py-gate/scripts/legacy.py order < "${TMPDIR:-/tmp}/py-gate-legacy.$$"
  rm -f "${TMPDIR:-/tmp}/py-gate-legacy.$$"
  exit 0
fi

# The project's packages: the import names under src/.
mapfile -t PKGS < <(find src -mindepth 2 -maxdepth 2 -name __init__.py -printf '%h\n' 2>/dev/null | xargs -r -n1 basename | sort)

fmt() {
  [ ${#FILES[@]} -gt 0 ] || return 0
  "${UV[@]}" ruff format --config ruff.toml --check --output-format concise --quiet --force-exclude "${RUFF_X[@]}" "${FILES[@]}" && return
  echo "Run bash py-gate/scripts/gate.sh --fix to format these files."
  return 1
}
# A dependency enters through stack add, or by the user's hand: py-gate/deps.txt
# lists the approved ones, so one an agent got in another way fails here.
approved() {
  [ -f py-gate/deps.txt ] || return 0
  python3 - <<'PY'
import re, sys, tomllib
from pathlib import Path
norm = lambda s: re.sub(r"[-_.]+", "-", re.split(r"[<>=!~;\[ @]", s.strip(), maxsplit=1)[0]).lower()
ok = {norm(l) for l in Path("py-gate/deps.txt").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}
j = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
pr = j.get("project", {})
reqs = [*pr.get("dependencies", []), *(d for g in pr.get("optional-dependencies", {}).values() for d in g),
        *(d for g in j.get("dependency-groups", {}).values() for d in g if isinstance(d, str))]
bad = sorted({norm(d) for d in reqs} - ok)
if bad:
    sys.exit(f"pyproject.toml has dependencies that the user did not approve: {', '.join(bad)}. "
             "Ask the user to remove each dependency with `uv remove <name>`, or to approve it. "
             "After the user approves a dependency, add its name on a new line in py-gate/deps.txt.")
PY
}
deps() {
  local args=(. --no-ansi --extend-exclude "py-gate/.*") p r
  for p in "${PKGS[@]}"; do args+=(--known-first-party "$p"); done
  # Added by stack before any code imports them: not reported as unused.
  [ ! -s py-gate/deptry.txt ] || args+=(--per-rule-ignores "DEP002=$(paste -sd'|' py-gate/deptry.txt)")
  while IFS= read -r r; do [ -z "$r" ] || args+=(--extend-exclude "$r"); done < <(python3 py-gate/conf.py exclude-regex)
  "${UV[@]}" deptry "${args[@]}"
}
cycles() {
  [ ${#PKGS[@]} -gt 0 ] || return 0
  local ini rc
  ini=$(mktemp)
  { echo "[importlinter]"; echo "root_packages ="; printf '    %s\n' "${PKGS[@]}"
    echo; echo "[importlinter:contract:acyclic]"; echo "name = No import cycles between sibling modules"
    echo "type = acyclic_siblings"; echo "ancestors ="; printf '    %s\n' "${PKGS[@]}"
    # The project's own contracts, its architecture record: kept by a re-install.
    [ ! -f py-gate/importlinter.ini ] || { echo; cat py-gate/importlinter.ini; }; } > "$ini"
  "${UV[@]}" lint-imports --config "$ini" --no-cache; rc=$?
  rm -f "$ini"
  return "$rc"
}
tests() {
  [ -d tests ] || { echo "no tests/ folder: no tests ran"; return 0; }
  local args=(-c pytest.toml -q --no-header) g rc
  for g in "${EXCLUDE[@]}"; do args+=(--ignore-glob "$g"); done
  # Workbench asks for each test's run time when it runs the project's checks.
  [ -z "${WORKSHOP_TEST_REPORTS:-}" ] || args+=(--junit-xml="$WORKSHOP_TEST_REPORTS/py-gate.xml" -o junit_family=xunit1)
  # pytest runs one test at a time: test_workers has nothing to bound.
  test_locked py-gate "$MODE" "${UV[@]}" pytest "${args[@]}"; rc=$?
  [ "$rc" -ne "$TEST_LOCK_TIMED_OUT" ] || return 1
  # 5: no test collected, as vitest's --passWithNoTests. Unless tests/ holds
  # test files: then a conftest or a marker hid them, and vitest's equal
  # sits in its guarded config, where pytest's is project code.
  if [ "$rc" -eq 5 ]; then
    [ -n "$(python3 py-gate/conf.py test-files)" ] || return 0
    echo "pytest collected no test, though tests/ holds test files: something in a conftest.py hides them. Remove it; leave a path out with exclude in .claude/workshop.conf, which the user decides"
  fi
  return "$rc"
}

run approved
run "${UV[@]}" ruff check --config ruff.toml --ignore-noqa --output-format concise --quiet --force-exclude "${RUFF_X[@]}" .
run fmt
# basedpyright skips every error in its baseline file, which
# `basedpyright --writebaseline` writes; the gate names one that never exists.
# It has no flag to leave a file out, so with a legacy list its JSON report
# loses the listed files' findings.
types() {
  [ ${#LEGACY[@]} -gt 0 ] || { quiet "${UV[@]}" "${PYRIGHT[@]}" "${PYRIGHT_PATHS[@]}"; return; }
  local out rc=0
  out=$("${UV[@]}" "${PYRIGHT[@]}" --outputjson "${PYRIGHT_PATHS[@]}") || rc=$?
  [ "$rc" -le 1 ] || { printf '%s\n' "$out"; return "$rc"; }
  printf '%s\n' "$out" | python3 py-gate/scripts/legacy.py pyright
}
run types
run "${UV[@]}" python py-gate/check.py
run quiet deps
run quiet cycles
run tests
if [ -z "$MODE" ] && [ ${#LEGACY[@]} -gt 0 ]; then
  echo "py-gate-legacy.txt: ${#LEGACY[@]} files the gate does not check yet. To bring one in, delete its line, then fix what the gate reports in it. The first line is the one to take next: ${LEGACY[0]}"
fi
exit $FAIL
