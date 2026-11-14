"""py-gate's own rules: what ruff and basedpyright cannot see or switch off.

usage: python py-gate/check.py   from the project root; one line per problem: path:line: rule: how to fix
Rules: python/gate/CLAUDE.md, "Rules".
"""

import ast
import collections
import fnmatch
import importlib.util
import io
import re
import sys
import tokenize
import tomllib
from pathlib import Path
from typing import Any

from conf import exclude, off

COMMENTS = [
    (
        re.compile(r"#\s*type:\s*ignore"),
        "no-ignore-comment",
        "the gate ignores type: ignore. Fix the type, or narrow it with isinstance",
    ),
    (
        re.compile(r"#\s*(pyright|basedpyright|ty|pyrefly|mypy)\s*:"),
        "no-ignore-comment",
        "a type checker comment turns its checks off. Fix the type instead",
    ),
    (
        re.compile(r"#\s*noqa\b|#\s*ruff\s*:"),
        "no-ignore-comment",
        "the gate runs ruff with --ignore-noqa, so this comment changes nothing. Fix the code and delete it",
    ),
    (
        re.compile(r"#\s*fmt\s*:\s*(off|on|skip)\b"),
        "no-format-comment",
        "the gate formats every line. Delete the comment and run the gate with --fix",
    ),
]
SKIPS = {"skip", "xfail", "importorskip"}
UNITTEST_SKIPS = {"skip", "expectedFailure", "SkipTest"}
CONDITIONS = {"skipif", "skipIf", "skipUnless"}
COLLECT = {"collect_ignore", "collect_ignore_glob", "pytest_ignore_collect"}
# The `type` statement is 3.12+; the gate runs on the project's Python, 3.11 at the lowest (tomllib).
TYPE_ALIAS = getattr(ast, "TypeAlias", ())
MOCK = (
    "no-module-mock: patching a module hides how the code gets its dependency. Pass the dependency in "
    "(an argument, a Protocol), or test through the public entry point"
)
SKIPPED = "no-disabled-test: a skipped test checks nothing. Make it pass, or delete it"
SKIPPED_IF = (
    "no-disabled-test: a constant condition skips the test every run. Make it pass, or delete it; "
    "a skipif stays only with a condition that can be false, such as the platform"
)
EXCLUDED = (
    "no-excluded: this imports `{}` from {}, which `exclude` in .claude/workshop.conf leaves out: "
    "what it holds can go at any time. Copy what the code needs out of it"
)
OBJECT_PARAM = (
    "no-object-signature: an `object` parameter takes input that is not parsed yet. Parse it where it "
    "arrives, with the project's schema library when it has one, and accept the named type. A dunder or "
    "@override method, the subject of a TypeGuard or TypeIs, a Callable's own types, and a validator "
    "whose decorator passes mode=\"before\", \"wrap\" or \"plain\" are exceptions"
)
OBJECT_RETURN = (
    "no-object-signature: an `object` return gives the caller a value it must parse again. Parse inside "
    "and return the named type"
)
LINE = re.compile(r"^(.+?):\d+: ([a-z-]+): ")
COLLECTED = (
    "no-disabled-test: `{}` hides test files from pytest. Leave a path out with `exclude` in "
    ".claude/workshop.conf, which the user decides"
)


def comments(path: Path, text: str) -> list[str]:
    out: list[str] = []
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return out
    for tok in toks:
        if tok.type == tokenize.COMMENT:
            for rx, rule, fix in COMMENTS:
                if rx.search(tok.string):
                    out.append(f"{path}:{tok.start[0]}: {rule}: {fix}")
                    break
    return out


def _is_pytest(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "pytest"


def _is_module(path: Path, node: ast.ImportFrom, name: str) -> bool:
    """Whether `from <node.module> import <name>` imports a module. Found on disk, never imported."""
    parts = [*(node.module or "").split("."), name]
    parts = [p for p in parts if p]
    if node.level:
        dirs = [path.parents[node.level - 1]]
    else:
        try:
            spec = importlib.util.find_spec(parts[0])
        except (ImportError, ValueError):
            return False
        if spec is None or len(parts) == 1:
            return spec is not None
        dirs = [Path(d) for d in spec.submodule_search_locations or []]
        parts = parts[1:]
    for d in dirs:
        target = d.joinpath(*parts)
        if target.is_dir() or target.with_suffix(".py").is_file():
            return True
    return False


def calls(path: Path, tree: ast.Module) -> list[str]:
    out: list[str] = []
    modules = {
        (a.asname or a.name).split(".")[0]
        for n in ast.walk(tree)
        if isinstance(n, ast.Import)
        for a in n.names
    } | {
        a.asname or a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)
        for a in n.names
        if a.name != "*" and _is_module(path, n, a.name)
    }
    # The fixture, and a name bound to `MonkeyPatch.context()` or `MonkeyPatch()`.
    patchers = {"monkeypatch"}
    for node in ast.walk(tree):
        bound: list[tuple[ast.expr, ast.expr | None]] = []
        if isinstance(node, (ast.With, ast.AsyncWith)):
            bound = [(i.context_expr, i.optional_vars) for i in node.items]
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            bound = [(node.value, node.targets[0])]
        for value, name in bound:
            if (
                isinstance(name, ast.Name)
                and isinstance(value, ast.Call)
                and (_last(value.func) == "MonkeyPatch" or (
                    isinstance(value.func, ast.Attribute)
                    and value.func.attr == "context"
                    and _last(value.func.value) == "MonkeyPatch"
                ))
            ):
                patchers.add(name.id)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr, owner = node.func.attr, node.func.value
            target = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "target"), None)
            if (
                isinstance(owner, ast.Name)
                and owner.id in patchers
                and attr in {"setattr", "delattr"}
                and target is not None
            ):
                t = target
                dotted = isinstance(t, ast.Constant) and isinstance(t.value, str) and "." in t.value
                module = isinstance(t, ast.Name) and t.id in modules
                submodule = (
                    isinstance(t, ast.Attribute)
                    and isinstance(t.value, ast.Name)
                    and t.value.id in modules
                    and t.attr[:1].islower()
                )
                if dotted or module or submodule:
                    out.append(f"{path}:{node.lineno}: {MOCK}")
    return out


def skips(path: Path, tree: ast.Module) -> list[str]:
    """Tests that never run: skip and xfail in pytest's and unittest's forms, and collection filters."""
    out: list[str] = []
    unittest = {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names if a.name == "unittest"}
    imported = {
        a.asname or a.name: a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module == "unittest" and not n.level
        for a in n.names
    }

    def name(node: ast.expr) -> str:
        """The unittest or pytest name an expression stands for: `skip`, `mark.skipif`, or ''."""
        if isinstance(node, ast.Name):
            return imported.get(node.id, "")
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in unittest or node.value.id == "pytest":
                return node.attr
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
            if node.value.attr == "mark" and _is_pytest(node.value.value):
                return f"mark.{node.attr}"
        return ""

    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute)):
            n = name(node)
            pytest_skip = isinstance(node, ast.Attribute) and (
                (_is_pytest(node.value) and n in SKIPS) or n in {"mark.skip", "mark.xfail"}
            )
            if pytest_skip or (n in UNITTEST_SKIPS and not _is_pytest(getattr(node, "value", node))):
                out.append(f"{path}:{node.lineno}: {SKIPPED}")
        if isinstance(node, ast.Attribute) and node.attr == "skipTest":
            out.append(f"{path}:{node.lineno}: {SKIPPED}")
        if isinstance(node, ast.Call) and name(node.func).removeprefix("mark.") in CONDITIONS:
            cond = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "condition"), None)
            if isinstance(cond, ast.Constant):
                out.append(f"{path}:{node.lineno}: {SKIPPED_IF}")
        if isinstance(node, ast.Name) and node.id in COLLECT:
            out.append(f"{path}:{node.lineno}: {COLLECTED.format(node.id)}")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in COLLECT:
            out.append(f"{path}:{node.lineno}: {COLLECTED.format(node.name)}")
    return out


def _module_file(path: Path, level: int, parts: list[str]) -> Path | None:
    """The project file an import names: under the importing file's package, or under src/ or the root.

    A .pyi beside the module comes first, as the type checker reads it: a kept stub of an excluded module is the
    interface the gate checks.
    """
    roots = [path.parents[level - 1]] if level else [Path("src"), Path()]
    for root in roots:
        target = root.joinpath(*parts)
        for f in (target.with_suffix(".pyi"), target / "__init__.pyi", target.with_suffix(".py"), target / "__init__.py"):
            if parts and f.is_file():
                return f
    return None


def excluded_imports(path: Path, tree: ast.Module, globs: list[str]) -> list[str]:
    """Imports of a module that `exclude` covers."""
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            named = [(0, a.name.split(".")) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = [p for p in (node.module or "").split(".") if p]
            named = [(node.level, base)] + [(node.level, [*base, a.name]) for a in node.names if a.name != "*"]
        else:
            continue
        for level, parts in named:
            f = _module_file(path, level, parts)
            if f is not None and any(fnmatch.fnmatch(f.as_posix(), g) for g in globs):
                out.append(f"{path}:{node.lineno}: {EXCLUDED.format('.' * level + '.'.join(parts), f.as_posix())}")
                break
    return out


def _last(node: ast.expr) -> str:
    return node.attr if isinstance(node, ast.Attribute) else node.id if isinstance(node, ast.Name) else ""


def _has_object(ann: ast.expr | None) -> bool:
    """Whether `object` is in an annotation, outside a Callable, whose types describe another function."""
    if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
        try:
            ann = ast.parse(ann.value, mode="eval").body
        except SyntaxError:
            return False
    if ann is None or (isinstance(ann, ast.Subscript) and _last(ann.value) == "Callable"):
        return False
    if isinstance(ann, (ast.Name, ast.Attribute)) and _last(ann) == "object":
        return isinstance(ann, ast.Name) or _last(ann.value) == "builtins"
    return any(_has_object(c) for c in ast.iter_child_nodes(ann) if isinstance(c, ast.expr))


def object_signatures(path: Path, tree: ast.Module) -> list[str]:
    """`object` in a signature, as ts-gate's no-unknown-signature refuses `unknown`."""
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        ret = node.returns
        guard = isinstance(ret, ast.Subscript) and _last(ret.value) in {"TypeGuard", "TypeIs"}
        dunder = node.name.startswith("__") and node.name.endswith("__")
        # An override's signature is its base's: typeshed's log_message takes *args: Any, which ruff refuses.
        # A decorator with mode="before", "wrap" or "plain" (a schema library's validator) is called
        # with the input before it is parsed: there `object` is the true type, and `Any` is refused.
        raw = any(
            isinstance(d, ast.Call)
            and any(
                k.arg == "mode" and isinstance(k.value, ast.Constant) and k.value.value in {"before", "wrap", "plain"}
                for k in d.keywords
            )
            for d in node.decorator_list
        )
        if guard or dunder or raw or any(_last(d) == "override" for d in node.decorator_list):
            continue
        a = node.args
        params = [*a.posonlyargs, *a.args, *a.kwonlyargs, *(p for p in (a.vararg, a.kwarg) if p)]
        out += [f"{path}:{p.lineno}: {OBJECT_PARAM}" for p in params if _has_object(p.annotation)]
        if isinstance(ret, (ast.Name, ast.Attribute)) and _last(ret) == "object":
            out.append(f"{path}:{node.lineno}: {OBJECT_RETURN}")
    return out


def defs(tree: ast.Module) -> list[tuple[str, ast.stmt]]:
    out: list[tuple[str, ast.stmt]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append((node.name, node))
        elif TYPE_ALIAS and isinstance(node, TYPE_ALIAS):
            out.append((node.name.id, node))
        elif isinstance(node, ast.Assign):
            out += [(t.id, node) for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.append((node.target.id, node))
    return [(n, d) for n, d in out if not (n.startswith("__") and n.endswith("__"))]


def uses(tree: ast.AST) -> collections.Counter[str]:
    names: collections.Counter[str] = collections.Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            names[node.id] += 1
        elif isinstance(node, ast.Attribute):
            names[node.attr] += 1
        elif isinstance(node, ast.ImportFrom):
            names.update(a.name for a in node.names)
    return names


def read_project() -> dict[str, Any]:
    try:
        return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8")).get("project", {})
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def entry_points(trees: dict[Path, ast.Module]) -> set[str]:
    """What a caller outside the package reaches: each __init__.py's imports and __all__, and the scripts."""
    names: set[str] = set()
    for path, tree in trees.items():
        if path.name == "__init__.py":
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    names.update(a.asname or a.name for a in node.names)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    names.add(node.value)
    project = read_project()
    targets = [
        *project.get("scripts", {}).values(),
        *project.get("gui-scripts", {}).values(),
        *(t for group in project.get("entry-points", {}).values() for t in group.values()),
    ]
    names.update(str(t).rpartition(":")[2].split(".")[0].strip() for t in targets)
    return names


def registered(node: ast.stmt, modules: set[str]) -> bool:
    """A decorator that calls a method of an object (`@app.command()`, `@router.get("/")`) registers the definition."""
    return any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and not (isinstance(d.func.value, ast.Name) and d.func.value.id in modules)
        for d in getattr(node, "decorator_list", [])
    )


def only_tests(src: dict[Path, ast.Module], tests: dict[Path, ast.Module]) -> list[str]:
    """Module-level names in src/ that no other code in src/ uses and no entry point names."""
    used = collections.Counter[str]()
    for tree in src.values():
        used.update(uses(tree))
    test_uses = collections.Counter[str]()
    for tree in tests.values():
        test_uses.update(uses(tree))
    entry = entry_points(src)
    out: list[str] = []
    for path, tree in src.items():
        if path.name == "__init__.py":
            continue
        modules = {(a.asname or a.name).split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        for name, node in defs(tree):
            # A use inside the definition itself (recursion, a method's return type) keeps nothing alive.
            if used[name] - uses(node)[name] > 0 or name in entry or registered(node, modules):
                continue
            if test_uses[name]:
                out.append(
                    f"{path}:{node.lineno}: only-tests-use: only tests use `{name}`. If code outside the "
                    "package calls it, import it in the package's __init__.py; if not, delete it and test "
                    "through the code that uses it"
                )
            else:
                out.append(
                    f"{path}:{node.lineno}: unused: nothing uses `{name}`. Delete it, or import it in the "
                    "package's __init__.py if code outside the package calls it"
                )
    return out


def scripts(project: dict[str, Any]) -> list[str]:
    """Each script and entry-point target that names a module or a name the project lacks."""
    groups = [project.get("scripts", {}), project.get("gui-scripts", {}), *project.get("entry-points", {}).values()]
    try:
        text = Path("pyproject.toml").read_text(encoding="utf-8").splitlines()
    except OSError:
        text = []
    out: list[str] = []
    for target in (str(t) for group in groups for t in group.values()):
        module, _, attr = target.split("[")[0].strip().partition(":")
        parts = module.strip().split(".")
        file = next((f for f in (Path("src", *parts).with_suffix(".py"), Path("src", *parts, "__init__.py")) if f.is_file()), None)
        line = next((i for i, row in enumerate(text, 1) if target in row), 1)
        where = f"pyproject.toml:{line}: entry-point: `{target}`"
        ask = "Write it, or ask the user to change pyproject.toml"
        if file is None:
            if Path("src", parts[0]).exists() or importlib.util.find_spec(parts[0]) is None:
                out.append(f"{where} names the module `{module}`, which does not exist. {ask}")
            continue
        head = attr.strip().split(".")[0]
        tree = ast.parse(file.read_text(encoding="utf-8"))
        names = {n for n, _ in defs(tree)} | {
            (a.asname or a.name).split(".")[0]
            for n in tree.body
            if isinstance(n, (ast.Import, ast.ImportFrom))
            for a in n.names
        }
        if head and head not in names:
            out.append(f"{where} names `{head}`, which {file} does not define. {ask}")
    return out


def files(root: str, globs: list[str]) -> list[Path]:
    return [
        p
        for p in sorted(Path(root).rglob("*.py"))
        if not any(fnmatch.fnmatch(p.as_posix(), g) for g in globs)
    ]


def parse(paths: list[Path], problems: list[str], globs: list[str]) -> dict[Path, ast.Module]:
    trees: dict[Path, ast.Module] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        problems += comments(path, text)
        try:
            trees[path] = ast.parse(text, str(path))
        except SyntaxError:
            continue
        tree = trees[path]
        problems += calls(path, tree) + skips(path, tree) + excluded_imports(path, tree, globs)
        problems += object_signatures(path, tree)
    return trees


def ruff_config() -> list[str]:
    """Settings in ruff.toml that replace py-gate's instead of adding to them. Across `extend`, ruff adds a
    project's ignore and extend-* settings to py-gate's, but its select, per-file-ignores or banned-api takes the
    place of py-gate's, and the rules or bans py-gate set are off without a word (probed, ruff 0.17.4)."""
    try:
        text = Path("ruff.toml").read_text(encoding="utf-8")
        project = tomllib.loads(text)
        gate = tomllib.loads(Path(__file__).with_name("ruff.gate.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    rows = text.splitlines()

    def line(pattern: str) -> int:
        return next((i for i, row in enumerate(rows, 1) if re.match(pattern, row.strip())), 1)

    def setting(table: dict[str, Any], key: str) -> object:
        lint = table.get("lint", {})
        return lint.get(key, table.get(key)) if isinstance(lint, dict) else table.get(key)

    out: list[str] = []
    where = "ruff.toml:{}: ruff-config: "
    if setting(project, "select") is not None:
        out.append(where.format(line(r"select\s*=")) + "select replaces py-gate's `ALL`. Turn a rule off with "
                   "ignore, or add one with extend-select")
    if setting(project, "per-file-ignores") is not None:
        out.append(where.format(line(r"\[(lint\.)?per-file-ignores\]|per-file-ignores\s*=")) + "per-file-ignores "
                   "replaces py-gate's, which keeps the test rules off. Use [lint.extend-per-file-ignores]")
    tidy, gate_tidy = setting(project, "flake8-tidy-imports"), setting(gate, "flake8-tidy-imports")
    banned = tidy.get("banned-api") if isinstance(tidy, dict) else None
    gate_banned = gate_tidy.get("banned-api", {}) if isinstance(gate_tidy, dict) else {}
    if isinstance(banned, dict) and isinstance(gate_banned, dict):
        missing = [k for k in gate_banned if k not in banned]
        if missing:
            out.append(where.format(line(r"\[(lint\.)?flake8-tidy-imports\.banned-api\]|banned-api\s*="))
                       + "ruff replaces py-gate's banned-api with this table, so its bans are off: copy "
                       f"py-gate/ruff.gate.toml's entries into it ({', '.join(missing)})")
    return out


def main() -> int:
    globs = exclude(Path())
    problems: list[str] = []
    src = parse(files("src", globs), problems, globs)
    # pytest loads a conftest.py in the rootdir, beside pytest.toml, as it does those in tests/.
    root_conftest = [Path("conftest.py")] if Path("conftest.py").is_file() else []
    tests = parse(files("tests", globs) + root_conftest, problems, globs)
    problems += only_tests(src, tests) + scripts(read_project()) + ruff_config()
    rules_off = off(Path())

    def kept(line: str) -> bool:
        m = LINE.match(line)
        return not m or not any(fnmatch.fnmatch(m[1], g) for g in rules_off.get(m[2], []))

    problems = [p for p in problems if kept(p)]
    for line in sorted(set(problems)):
        print(line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
