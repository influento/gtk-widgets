"""CPU power level: the energy performance preference (EPP) that intel_pstate
and amd-pstate-epp take per CPU. Set through the root helper; the popup's pick
is stored, and `settings-epp restore` sets it again at sway startup, since
the kernel starts with its default (stdlib)."""

import os
import subprocess
import sys
from pathlib import Path

from gtk_widgets.widgets.settings.state import STATE_DIR, write_state

LEVELS = ("performance", "balance_performance", "balance_power", "power")
EPP_FILES = "cpu[0-9]*/cpufreq/energy_performance_preference"
CPU_DIR = Path("/sys/devices/system/cpu")
HELPER = "/usr/lib/gtk-widgets/epp-helper"
STATE_FILE = STATE_DIR / "epp"


class EppFailed(RuntimeError):
    """Setting or restoring the level failed; the message is shown as it is."""


def available() -> bool:
    return any(CPU_DIR.glob(EPP_FILES))


def current() -> str | None:
    """The level every CPU has; None when they differ or there is no EPP."""
    levels = {path.read_text().strip() for path in CPU_DIR.glob(EPP_FILES)}
    return levels.pop() if len(levels) == 1 else None


def apply(level: str) -> EppFailed | None:
    # widget-toggle's LD_PRELOAD makes the setuid pkexec's loader complain on
    # stderr, which is the failure message
    env = {k: v for k, v in os.environ.items() if k != "LD_PRELOAD"}
    try:
        result = subprocess.run(
            ["pkexec", HELPER, level],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except OSError as e:
        return EppFailed(str(e))
    if result.returncode == 0:
        return None
    return EppFailed(result.stderr.strip() or f"epp-helper exited {result.returncode}")


def pick(level: str) -> EppFailed | None:
    """Set the level now and store it for the next sway startup."""
    failed = apply(level)
    if failed is None:
        write_state(STATE_FILE, f"{level}\n")
    return failed


def restore() -> EppFailed | None:
    """Set the stored level; nothing to do when none is stored."""
    try:
        level = STATE_FILE.read_text().strip()
    except FileNotFoundError:
        return None
    except OSError as e:
        return EppFailed(f"{STATE_FILE}: {e.strerror}")
    if level not in LEVELS:
        return EppFailed(f"{STATE_FILE}: {level!r} is not one of {', '.join(LEVELS)}")
    return apply(level)


def run(argv: list[str]) -> int:
    if argv != ["restore"]:
        print("usage: settings-epp restore", file=sys.stderr)
        return 2
    match restore():
        case None:
            return 0
        case EppFailed() as failed:
            print(f"settings-epp: {failed}", file=sys.stderr)
            return 1


def main() -> int:
    return run(sys.argv[1:])
