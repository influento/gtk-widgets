"""Read .claude/workshop.conf (the key table: AGENTS.md in the workshop repo).

usage: python3 py-gate/conf.py exclude        the exclude globs, one per line
       python3 py-gate/conf.py exclude-regex  the same as regular expressions (deptry takes those)
       python3 py-gate/conf.py test-files     pytest's test files under tests/ that no glob excludes
       python3 py-gate/conf.py pyright-paths  pyrightconfig.json's include paths that exist, when one does not
       python3 py-gate/conf.py target-version ruff's target (py314) from requires-python's lowest 3.x; none prints nothing
       python3 py-gate/conf.py legacy         the files py-gate-legacy.txt lists, one per line
       python3 py-gate/conf.py ruff-legacy    the same as one ruff setting, for its --config
       python3 py-gate/conf.py requirements [<group>]
                                              the names pyproject.toml requires, normalized; with a group, that
                                              dependency group's only
       python3 py-gate/conf.py unapproved     the names pyproject.toml requires that py-gate/deps.txt lacks
"""

import fnmatch
import json
import re
import sys
import tomllib
from pathlib import Path


def workshop_conf(root: Path) -> dict[str, str]:
    """A byte that is not UTF-8 is kept (surrogateescape), as legacy() keeps it: a glob names the path's own
    bytes, and a stray byte in a comment breaks nothing."""
    conf: dict[str, str] = {}
    try:
        data = (root / ".claude" / "workshop.conf").read_bytes()
    except OSError:
        return conf
    for raw in data.decode("utf-8", "surrogateescape").split("\n"):
        line = raw.strip()
        key, eq, value = line.partition("=")
        if line and not line.startswith("#") and eq and key.strip():
            conf[key.strip()] = value.strip()
    return conf


def globs(value: str) -> list[str]:
    return [g.strip() for g in value.split(",") if g.strip()]


def exclude(root: Path) -> list[str]:
    return globs(workshop_conf(root).get("exclude", ""))


LEGACY = "py-gate-legacy.txt"


def legacy(root: Path) -> list[str]:
    """The files that failed the gate when py-gate came into the project, which it does not check yet.
    Read as scripts/legacy-list.py reads the list: split on \\n only, and a byte that is not UTF-8 kept
    (surrogateescape), so each line that check passes names the one file it names there."""
    try:
        data = (root / LEGACY).read_bytes()
    except OSError:
        return []
    rows = (row.strip() for row in data.decode("utf-8", "surrogateescape").split("\n"))
    return [row for row in rows if row and not row.startswith("#")]


def ruff_legacy(root: Path) -> str:
    """The listed files as ruff's `extend-exclude`, each a glob that matches that file alone: its glob
    characters escaped (`[ab].py` would match `a.py` and not itself), from the root (`m.py` would match
    `sub/m.py` too), in a TOML array (ruff's --extend-exclude splits its value at each comma). A byte that
    is not UTF-8 is `?`: ruff matches a lossy copy of the path."""
    escaped = (re.sub(r"[\\*?[\]{}]", r"\\\g<0>", p) for p in legacy(root))
    return "extend-exclude = " + json.dumps(["./" + re.sub("[\udc80-\udcff]", "?", p) for p in escaped])


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


def requirement_name(spec: str) -> str:
    """A requirement's name, normalized as PEP 503 compares names: `Left_Pad>=1` and `left-pad` are one."""
    m = re.match(r"[A-Za-z0-9._-]*", spec.strip())
    return re.sub(r"[-_.]+", "-", m[0] if m else "").lower()


def requirements(root: Path, group: str | None = None) -> list[str]:
    """The names pyproject.toml requires: [project] dependencies and optional-dependencies, and every
    [dependency-groups] group; with a group, that group's only. A missing or broken pyproject.toml raises."""
    j = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    groups = j.get("dependency-groups", {})
    if group is not None:
        specs = groups.get(group, [])
    else:
        project = j.get("project", {})
        specs = [*project.get("dependencies", []), *(d for g in project.get("optional-dependencies", {}).values() for d in g),
                 *(d for g in groups.values() for d in g)]
    # A {include-group = ...} entry names a group, not a requirement.
    return list(dict.fromkeys(requirement_name(d) for d in specs if isinstance(d, str)))


DEPS = "py-gate/deps.txt"


def approved(root: Path) -> list[str]:
    """The names in py-gate/deps.txt, the dependencies the user approved, as written."""
    text = (root / DEPS).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def target_version(root: Path) -> str:
    """ruff's --target-version: with --config, ruff no longer reads requires-python (probed, ruff 0.17.4)."""
    try:
        spec = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["requires-python"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError):
        return ""
    m = re.search(r"3\.(\d+)", str(spec))
    return f"py3{m[1]}" if m else ""


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="surrogateescape")
    if sys.argv[1:] == ["exclude"]:
        for g in exclude(Path()):
            print(g)
    elif sys.argv[1:] == ["exclude-regex"]:
        for g in exclude(Path()):
            print(fnmatch.translate(g))
    elif sys.argv[1:] == ["pyright-paths"]:
        for p in pyright_paths(Path()):
            print(p)
    elif sys.argv[1:] == ["legacy"]:
        for p in legacy(Path()):
            print(p)
    elif sys.argv[1:] == ["ruff-legacy"]:
        print(ruff_legacy(Path()))
    elif sys.argv[1:2] == ["requirements"] and len(sys.argv) <= 3:
        for n in requirements(Path(), *sys.argv[2:]):
            print(n)
    elif sys.argv[1:] == ["unapproved"]:
        ok = {requirement_name(n) for n in approved(Path())}
        for n in sorted(set(requirements(Path())) - ok):
            print(n)
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
