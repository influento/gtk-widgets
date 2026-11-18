"""Saves through a temp file of their own: a second writer mid-save (the timer
popup and timer-status, a voice apply and the popup's flush) keeps its file."""

import os
import subprocess
import sys
from pathlib import Path

from gtk_widgets.lib.paths import SRC

HALF_WRITTEN = "another writer's half-written file"


def _run(code: str, env: dict[str, str]) -> None:
    env = {**os.environ, **env, "PYTHONPATH": str(SRC)}
    _ = subprocess.run([sys.executable, "-c", code], env=env, check=True)


def test_voice_settings_save_leaves_another_writers_temp_file_alone(
    tmp_path: Path,
) -> None:
    settings = tmp_path / "gtk-widgets" / "audio-voice.json"
    settings.parent.mkdir()
    other = settings.with_name(settings.name + ".tmp")
    _ = other.write_text(HALF_WRITTEN)
    _run(
        "from gtk_widgets.widgets.audio.voice import apply; "
        "from gtk_widgets.widgets.audio.parse import Voice; "
        "assert apply(Voice(), 'mic', mode='save', switched=False) == 'save'",
        {"XDG_CONFIG_HOME": str(tmp_path)},
    )
    assert other.read_text() == HALF_WRITTEN
    assert '"on": false' in settings.read_text()


def test_timer_state_save_leaves_another_writers_temp_file_alone(
    tmp_path: Path,
) -> None:
    state = tmp_path / "gtk-widgets-timer.json"
    other = state.with_name(state.name + ".tmp")
    _ = other.write_text(HALF_WRITTEN)
    _run(
        "from gtk_widgets.widgets.timer.state import save; "
        "from gtk_widgets.widgets.timer.parse import State; "
        "save(State())",
        {"XDG_RUNTIME_DIR": str(tmp_path)},
    )
    assert other.read_text() == HALF_WRITTEN
    assert state.read_text().startswith("{")
