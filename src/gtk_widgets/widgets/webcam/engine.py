"""Start, stop and find the effects engine (`webcam-effects`), stdlib. The
engine holds an flock on its lock file while it runs, with its pid inside;
its output goes to a log beside it, which the popup shows when it fails."""

import contextlib
import fcntl
import os
import signal
import subprocess
from pathlib import Path

from gtk_widgets.lib.paths import module_child

ENGINE_MODULE = "gtk_widgets.widgets.webcam.effects"


def runtime_dir() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")


def lock_file() -> Path:
    return runtime_dir() / "webcam-effects.lock"


def log_file() -> Path:
    return runtime_dir() / "webcam-effects.log"


def running_pid() -> int | None:
    """The engine's pid while it runs."""
    try:
        fd = os.open(lock_file(), os.O_RDONLY)
    except OSError:
        return None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            text = os.read(fd, 32).decode(errors="replace").strip()
            return int(text) if text.isdigit() else None
        return None  # nobody holds it: the engine is gone
    finally:
        os.close(fd)


def start() -> subprocess.Popen[bytes]:
    """Start the engine detached; it outlives the popup."""
    argv, env = module_child(ENGINE_MODULE)
    log_file().parent.mkdir(parents=True, exist_ok=True)
    with log_file().open("wb") as log:
        return subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            env=env,
            start_new_session=True,
        )


def stop() -> None:
    pid = running_pid()
    if pid is not None:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)


def last_error() -> str:
    """The log's last line: why the engine stopped."""
    try:
        lines = log_file().read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return next((line for line in reversed(lines) if line.strip()), "")
