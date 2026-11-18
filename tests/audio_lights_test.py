"""The mic lights file's parser, effects, saves and the frame the daemon sends."""

import json
import math
import os
import subprocess
import sys
from pathlib import Path

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.lib.paths import SRC
from gtk_widgets.widgets.audio.lights import (
    RGB,
    WAVE_LAG,
    Status,
    colour_packet,
    header_packet,
    parts_at,
)
from gtk_widgets.widgets.audio.parse import Lights, parse_lights


def test_missing_fields_take_defaults() -> None:
    assert parse_lights({"on": True}) == Lights(on=True)


def test_rejects_a_colour_that_is_not_hex() -> None:
    result = parse_lights({"top": "red"})
    assert isinstance(result, ParseError)
    assert ".top" in str(result)


def test_rejects_brightness_out_of_range() -> None:
    assert isinstance(parse_lights({"brightness": 101}), ParseError)


def test_frame_is_top_then_bottom_scaled_by_brightness() -> None:
    packet = colour_packet((255.0, 128.0, 0.0), (0.0, 0.0, 255.0), 50)
    assert packet[:8] == bytes([0x81, 128, 64, 0, 0x81, 0, 0, 128])
    assert len(packet) == 64
    assert packet[8:] == bytes(56)


def test_header_announces_one_frame() -> None:
    packet = header_packet()
    assert packet[:2] == bytes([0x04, 0xF2])
    assert packet[8] == 1
    assert len(packet) == 64


def _at(lights: Lights, t: float, status: Status | None = None) -> tuple[RGB, RGB]:
    return parts_at(lights, t, status or Status())


RED, BLUE = (255.0, 0.0, 0.0), (0.0, 48.0, 255.0)


def test_solid_is_the_part_colours() -> None:
    assert _at(Lights(top="#ff0000", bottom="#0030ff"), 7.0) == (RED, BLUE)


def test_voice_is_dim_when_silent_and_full_when_loud() -> None:
    lights = Lights(effect="voice", top="#ff0000", bottom="#ff0000")
    silent, _ = _at(lights, 0.0, Status(level=0.0))
    loud, _ = _at(lights, 0.0, Status(level=1.0))
    assert 0 < silent[0] < 64
    assert loud == RED


def test_blink_one_colour_goes_on_and_off() -> None:
    lights = Lights(
        effect="blink", colours=["#ff0000"], speed=0
    )  # 2 s: 1 s on, 1 s off
    assert _at(lights, 0.5) == (RED, RED)
    assert _at(lights, 1.5) == ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


def test_pulse_is_dark_at_the_start_and_full_halfway() -> None:
    lights = Lights(effect="pulse", colours=["#ff0000"], speed=0)  # 6 s per pulse
    assert _at(lights, 0.0)[0] == (0.0, 0.0, 0.0)
    top, bottom = _at(lights, 3.0)
    assert top == bottom
    assert round(top[0]) == 255


def test_cycle_moves_both_parts_together_and_wave_splits_them() -> None:
    colours = ["#ff0000", "#00ff20"]
    top, bottom = _at(Lights(effect="cycle", colours=colours), 1.0)
    assert top == bottom
    top, bottom = _at(Lights(effect="wave", colours=colours), 1.0)
    assert top != bottom


def test_lightning_flashes_then_goes_dark() -> None:
    lights = Lights(effect="lightning", colours=["#ff0000"], speed=100)
    tops = [_at(lights, n * 0.055)[0][0] for n in range(200)]
    assert max(tops) > 200
    assert min(tops) < 5


def test_a_dropped_effect_is_solid_with_the_other_settings() -> None:
    lights = parse_lights({"on": True, "effect": "in_use", "top": "#00ff20"})
    assert lights == Lights(on=True, effect="solid", top="#00ff20")


def test_wave_just_before_the_top_starts_its_first_turn() -> None:
    # float % can give 1.0 for a turn a hair below 0: the colour index must stay in range
    lights = Lights(
        effect="wave", colours=["#ff0000", "#00ff20"]
    )  # speed 50: 11 s a turn
    top, bottom = _at(lights, math.nextafter(WAVE_LAG * 11.0, 0))
    assert all(0 <= c <= 255 for c in (*top, *bottom))


def test_the_daemon_never_loads_gtk() -> None:
    # audio-lights has no window: GTK would make it a compositor client
    code = "import sys, gtk_widgets.widgets.audio.lightsd; sys.exit('gi.repository.Gtk' in sys.modules)"
    env = {**os.environ, "LD_PRELOAD": "", "PYTHONPATH": str(SRC)}
    assert (
        subprocess.run([sys.executable, "-c", code], env=env, check=False).returncode
        == 0
    )


def test_a_save_leaves_another_writers_temp_file_alone(tmp_path: Path) -> None:
    settings = tmp_path / "gtk-widgets" / "audio-lights.json"
    settings.parent.mkdir()
    other = settings.with_name(settings.name + ".tmp")  # mid-write elsewhere
    _ = other.write_text("another writer's half-written settings")
    code = (
        "from gtk_widgets.widgets.audio.lights import apply; "
        "from gtk_widgets.widgets.audio.parse import Lights; "
        "assert apply(Lights(on=True), switched=False) is None"
    )
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path), "PYTHONPATH": str(SRC)}
    _ = subprocess.run([sys.executable, "-c", code], env=env, check=True)
    assert other.read_text() == "another writer's half-written settings"
    assert parse_lights(json.loads(settings.read_text())) == Lights(on=True)
