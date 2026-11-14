"""Read .claude/workshop.conf (the key table: AGENTS.md in the workshop repo).

usage: python3 py-gate/conf.py exclude        the exclude globs, one per line
       python3 py-gate/conf.py exclude-regex  the same as regular expressions (deptry takes those)
       python3 py-gate/conf.py test-files     pytest's test files under tests/ that no glob excludes
       python3 py-gate/conf.py pyright-paths  pyrightconfig.json's include paths that exist, when one does not
       python3 py-gate/conf.py target-version ruff's target (py314) from requires-python's lowest 3.x; none prints nothing
"""

import fnmatch
import json
import re
import sys
import tomllib
from pathlib import Path


def workshop_conf(root: Path) -> dict[str, str]:
    conf: dict[str, str] = {}
    try:
        text = (root / ".claude" / "workshop.conf").read_text(encoding="utf-8")
    except OSError:
        return conf
    for raw in text.split("\n"):
        line = raw.strip()
        key, eq, value = line.partition("=")
        if line and not line.startswith("#") and eq and key.strip():
            conf[key.strip()] = value.strip()
    return conf


def globs(value: str) -> list[str]:
    return [g.strip() for g in value.split(",") if g.strip()]


def exclude(root: Path) -> list[str]:
    return globs(workshop_conf(root).get("exclude", ""))


def off(root: Path) -> dict[str, list[str]]:
    """`py-gate.off.<rule> = <globs>`: check.py's rule <rule> is off in the files the globs match."""
    prefix = "py-gate.off."
    return {k.removeprefix(prefix): globs(v) for k, v in workshop_conf(root).items() if k.startswith(prefix) and globs(v)}


def pyright_paths(root: Path) -> list[str]:
    """basedpyright exits 3 when an include path is missing, as tests/ is in a new project: name the ones that exist."""
    try:
        include = json.loads((root / "pyrightconfig.json").read_text(encoding="utf-8")).get("include", [])
    except (OSError, ValueError, AttributeError):
        return []
    paths = [str(p) for p in include if isinstance(p, str)]
    present = [p for p in paths if (root / p).exists()]
    return present if present != paths else []


def target_version(root: Path) -> str:
    """ruff's --target-version: with --config, ruff no longer reads requires-python (probed, ruff 0.17.4)."""
    try:
        spec = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["requires-python"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError):
        return ""
    m = re.search(r"3\.(\d+)", str(spec))
    return f"py3{m[1]}" if m else ""


if __name__ == "__main__":
    if sys.argv[1:] == ["exclude"]:
        for g in exclude(Path()):
            print(g)
    elif sys.argv[1:] == ["exclude-regex"]:
        for g in exclude(Path()):
            print(fnmatch.translate(g))
    elif sys.argv[1:] == ["pyright-paths"]:
        for p in pyright_paths(Path()):
            print(p)
    elif sys.argv[1:] == ["target-version"]:
        v = target_version(Path())
        if v:
            print(v)
    elif sys.argv[1:] == ["test-files"]:
        globs = exclude(Path())
        for p in sorted(Path("tests").rglob("*.py")):
            named = p.name.startswith("test_") or p.name.endswith("_test.py")
            if named and not any(fnmatch.fnmatch(p.as_posix(), g) for g in globs):
                print(p)
