"""py-gate-legacy.txt: the files that failed the gate when py-gate came into an existing project.

usage: ... basedpyright --outputjson | python3 py-gate/scripts/legacy.py pyright
           its findings outside the listed files, as text; exit 1 when an error is left
       ... | python3 py-gate/scripts/legacy.py paths
           the files that tool output names: `path:line:` lines, and basedpyright's JSON errors
       ... | uv run python py-gate/scripts/legacy.py order
           those files with a module before the modules that import it, then the rest by path
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conf import legacy  # py-gate/conf.py, beside scripts/

LINE = re.compile(r"^(\S+?\.pyi?):\d+")


def diagnostics(text: str) -> list[dict[str, object]] | None:
    try:
        found = json.loads(text).get("generalDiagnostics", [])
    except (ValueError, AttributeError):
        return None
    return [d for d in found if isinstance(d, dict)] if isinstance(found, list) else None


def relative(file: object) -> str:
    path = Path(str(file))
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def where(d: dict[str, object]) -> str:
    start = d.get("range", {})
    start = start.get("start", {}) if isinstance(start, dict) else {}
    line = start.get("line", 0) if isinstance(start, dict) else 0
    col = start.get("character", 0) if isinstance(start, dict) else 0
    return f"{relative(d.get('file'))}:{int(line) + 1}:{int(col) + 1}"


def pyright(text: str) -> int:
    found = diagnostics(text)
    if found is None:
        print(text)
        return 1
    listed = set(legacy(Path()))
    kept = [d for d in found if relative(d.get("file")) not in listed and d.get("severity") in {"error", "warning"}]
    for d in kept:
        rule = f" ({d['rule']})" if d.get("rule") else ""
        print(f"{where(d)} - {d.get('severity')}: {d.get('message')}{rule}")
    errors = sum(d.get("severity") == "error" for d in kept)
    if kept:
        print(f"{errors} errors, {len(kept) - errors} warnings")
    return 1 if errors else 0


def paths(text: str) -> list[str]:
    found = diagnostics(text)
    if found is not None:
        return sorted({relative(d.get("file")) for d in found if d.get("severity") == "error"})
    return sorted({m[1] for line in text.splitlines() if (m := LINE.match(line))})


def module(path: str) -> str | None:
    parts = Path(path).with_suffix("").parts
    if len(parts) < 3 or parts[0] != "src":
        return None
    names = list(parts[1:])
    if names[-1] == "__init__":
        names.pop()
    return ".".join(names)


def order(files: list[str]) -> list[str]:
    """A module comes after every listed module it imports, so the first lines are the ones to take first: a
    module that imports an unchecked one gets its unknown types. Without grimp (import-linter's), by path."""
    mods = {f: m for f in files if (m := module(f))}
    try:
        import grimp  # in the project's environment only, through import-linter

        graph = grimp.build_graph(*sorted({m.split(".")[0] for m in mods.values()}))
        listed = set(mods.values())

        def depth(f: str) -> int:
            return len(graph.find_upstream_modules(mods[f]) & listed)

        first = sorted(mods, key=lambda f: (depth(f), f))
    except Exception:  # no grimp, or a module it cannot read: the order is only advice
        first = sorted(mods)
    return first + sorted(f for f in files if f not in mods)


if __name__ == "__main__":
    cmd = sys.argv[1:]
    stdin = sys.stdin.read()
    if cmd == ["pyright"]:
        sys.exit(pyright(stdin))
    elif cmd == ["paths"]:
        for p in paths(stdin):
            print(p)
    elif cmd == ["order"]:
        for p in order(sorted({line.strip() for line in stdin.splitlines() if line.strip()})):
            print(p)
    else:
        sys.exit(__doc__)
