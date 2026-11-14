---
name: py-practices
description: Python practice - parsing outside data (files, JSON, HTTP bodies, argv) into typed models, annotations, Python 3.14 syntax, async code, tests. Use before writing or changing any Python code.
---

# Python practices

- Parse outside data (TOML and JSON files, HTTP bodies, command-line input) with the project's schema library (pydantic, msgspec, attrs with cattrs: `pyproject.toml` lists it) into typed models where it enters, in strict mode so that `"5"` is not an integer. The rest of the code takes the models, never `dict[str, Any]`.
- Trust the annotations: do not check at run time what a parameter's type already says.
- Write the syntax of the project's Python (`requires-python`): on 3.14, no `from __future__ import annotations`; write `X | None`, `list[int]` and `type` aliases.
- Keep a function synchronous unless the task asks for async. In async code, run concurrent work in an `asyncio.TaskGroup` and bound it with `asyncio.timeout`.
- Annotate every function, tests included.
- A test calls the code the way its users do: pass a dependency in rather than patch a module (`main(argv)`, not `sys.argv`).
- `pytest.raises` names the exception and a `match`.
