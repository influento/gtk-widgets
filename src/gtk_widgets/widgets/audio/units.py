"""The commands behind voice processing's and the mic lights' user units
(stdlib)."""

import subprocess

COMMAND_TIMEOUT_S = 15


def run(*argv: str) -> str | None:
    """None when the command succeeded, else why it failed."""
    try:
        done = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"{' '.join(argv)}: {e}"
    if done.returncode:
        return done.stderr.strip() or f"{' '.join(argv)}: exit {done.returncode}"
    return None


def systemctl(*args: str) -> str | None:
    return run("systemctl", "--user", *args)
