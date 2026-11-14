"""Run GTK on a private headless Sway, so no window reaches the desktop."""

import ctypes
import os
import shutil
import tempfile
import time
from pathlib import Path

import gi
import pytest
from gi.repository import Gio, GLib

# gtk4-layer-shell has to load before libwayland-client, which Gtk loads.
_ = ctypes.CDLL("libgtk4-layer-shell.so.0", mode=ctypes.RTLD_GLOBAL)

# Sway outlives a pytest that `timeout` or a kill ends before unconfigure: a
# watchdog, started by Sway, ends Sway and removes its runtime dir then.
_SWAY_CONFIG = "output HEADLESS-1 resolution 1280x720\nexec sh {watchdog}\n"
_WATCHDOG = """while kill -0 {pid} 2>/dev/null; do sleep 1; done
swaymsg exit
rm -rf '{runtime}'
"""
_sway: list[tuple[Gio.Subprocess, Path]] = []


def pytest_configure(config: pytest.Config) -> None:
    del config
    gi.require_versions({"Gtk": "4.0", "Gdk": "4.0", "Gtk4LayerShell": "1.0"})
    # A socket path has a 108-byte limit, so the runtime dir, not a tmp_path.
    runtime = Path(tempfile.mkdtemp(prefix="sway-", dir=GLib.get_user_runtime_dir()))
    sway_config = runtime / "config"
    watchdog = runtime / "watchdog.sh"
    _ = watchdog.write_text(
        _WATCHDOG.format(pid=os.getpid(), runtime=runtime), encoding="utf-8"
    )
    _ = sway_config.write_text(_SWAY_CONFIG.format(watchdog=watchdog), encoding="utf-8")
    launcher = Gio.SubprocessLauncher.new(
        Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE
    )
    for name in ("WAYLAND_DISPLAY", "DISPLAY", "SWAYSOCK", "I3SOCK"):
        launcher.unsetenv(name)
    for name, value in (
        ("XDG_RUNTIME_DIR", str(runtime)),
        ("SWAYSOCK", str(runtime / "sway.sock")),
        ("WLR_BACKENDS", "headless"),
        ("WLR_LIBINPUT_NO_DEVICES", "1"),
        ("WLR_RENDERER", "pixman"),
    ):
        launcher.setenv(name, value, overwrite=True)
    _sway.append((launcher.spawnv(["sway", "--config", str(sway_config)]), runtime))
    deadline = time.monotonic() + 5
    while not (locks := list(runtime.glob("wayland-*.lock"))):
        if time.monotonic() > deadline:
            msg = "headless sway opened no Wayland socket in 5 s"
            raise RuntimeError(msg)
        time.sleep(0.01)
    _ = os.environ.pop("DISPLAY", None)
    os.environ["GDK_BACKEND"] = "wayland"
    os.environ["WAYLAND_DISPLAY"] = str(locks[0].with_suffix(""))
    os.environ["SWAYSOCK"] = str(runtime / "sway.sock")


def pytest_unconfigure(config: pytest.Config) -> None:
    del config
    for sway, runtime in _sway:
        sway.force_exit()
        _ = sway.wait(None)
        shutil.rmtree(runtime, ignore_errors=True)
