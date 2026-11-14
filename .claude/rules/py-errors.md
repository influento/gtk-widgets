---
paths: ["**/*.py"]
---

# Errors

- A failure the caller must handle (not found, invalid input, a refused
  request): return it. `def find(...) -> User | UserNotFound`, and the
  caller handles each case with `match`; the gate reports a missing case.
  A raised exception is not in the signature: nothing tells the caller it
  missed one.
- A bug, or a failure no caller can act on: raise.
- The project's exception classes subclass the closest built-in (bad
  input: `ValueError`; not found: `LookupError`), not bare `Exception`.
