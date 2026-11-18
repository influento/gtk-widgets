"""HyperX QuadCast S lights: the settings file, the user unit that runs
`audio-lights` (lightsd.py) and the frames it sends (stdlib).

The mic has two parts (top, bottom), one colour each per frame, and shows
them only while the host keeps sending frames (every 55 ms); it falls back to
its own rainbow when they stop. So the lights are on while the unit runs: the
popup enables it (back at every login) and disables it, and the daemon follows
the settings file for every other change. An effect is a function of time
(and of the sound server's status) to the two colours: parts_at().
"""

import colorsys
import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from gtk_widgets.lib.files import replace_text
from gtk_widgets.lib.parse import ParseError
from gtk_widgets.widgets.audio.parse import PERCENT, Lights, parse_lights
from gtk_widgets.widgets.audio.units import systemctl

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
SETTINGS_FILE = CONFIG_HOME / "gtk-widgets" / "audio-lights.json"
UNIT = "gtk-widgets-mic-lights.service"
UNIT_FILE = CONFIG_HOME / "systemd" / "user" / UNIT
DAEMON = "audio-lights"  # lightsd.py; install.sh writes its launcher

VENDOR, PRODUCT = 0x0951, 0x171F  # the mic's lights controller (its audio is 171d)
USB_DEVICES = Path("/sys/bus/usb/devices")
PACKET_SIZE = 64
HEADER_CODE, DISPLAY_CODE, FRAME_COUNT = 0x04, 0xF2, 0x01
COLOUR_CODE = 0x81
FULL_BRIGHTNESS = 100
type RGB = tuple[float, float, float]  # 0-255 each
BLACK: RGB = (0.0, 0.0, 0.0)
# (slowest, fastest) in seconds, at speed 0 and 100
PULSE_PERIOD_S = (6.0, 0.8)  # one fade in and out
CYCLE_PERIOD_S = (20.0, 2.0)  # once round the colours (cycle, wave)
BLINK_PERIOD_S = (2.0, 0.2)  # on + off, or two colour changes
LIGHTNING_INTERVAL_S = (5.0, 0.6)  # one flash per part in each
LIGHTNING_SPREAD = 0.7  # a flash starts in the first 70% of its interval
LIGHTNING_FADE_S = 0.25
WAVE_LAG = 0.15  # turns the top runs behind the bottom
VOICE_FLOOR = 0.08  # brightness share while silent
OFF = "#000000"
# Swatches the popup offers: saturated colours, as LEDs show pastels as white
COLOURS = (
    ("Red", "#ff0000"),
    ("Orange", "#ff6000"),
    ("Yellow", "#ffd000"),
    ("Green", "#00ff20"),
    ("Cyan", "#00ffd0"),
    ("Blue", "#0030ff"),
    ("Purple", "#8000ff"),
    ("Pink", "#ff00a0"),
    ("White", "#ffffff"),
    ("Off", OFF),
)

UNIT_TEXT = f"""[Unit]
Description=gtk-widgets HyperX QuadCast S lights

[Service]
Type=simple
# set, so importing lib.ui (the voice meter) skips its gtk4-layer-shell re-exec
Environment=LD_PRELOAD=
ExecStart=%h/.local/bin/{DAEMON}
Restart=on-failure
RestartSec=2
Slice=session.slice

[Install]
WantedBy=default.target
"""


class LightsError(RuntimeError):
    """A settings file or unit that could not be written, or a failed systemctl."""


def present() -> bool:
    """The mic is plugged in (sysfs, no libusb)."""
    want = (f"{VENDOR:04x}", f"{PRODUCT:04x}")
    for device in USB_DEVICES.glob("*"):
        try:
            ids = (
                (device / "idVendor").read_text().strip(),
                (device / "idProduct").read_text().strip(),
            )
        except OSError:
            continue
        if ids == want:
            return True
    return False


def header_packet() -> bytes:
    return bytes([HEADER_CODE, DISPLAY_CODE, *[0] * 6, FRAME_COUNT]).ljust(
        PACKET_SIZE, b"\0"
    )


def colour_packet(top: RGB, bottom: RGB, brightness: int) -> bytes:
    """One frame: the top part's colour, then the bottom's, at the brightness."""

    def part(colour: RGB) -> bytes:
        level = brightness / FULL_BRIGHTNESS
        return bytes(
            [COLOUR_CODE, *(min(255, max(0, round(c * level))) for c in colour)]
        )

    return (part(top) + part(bottom)).ljust(PACKET_SIZE, b"\0")


@dataclass(frozen=True, slots=True)
class Status:
    """What the status effects follow, from the sound server."""

    level: float = 0.0  # the mic's loudness, 0-1


def rgb(colour: str) -> RGB:
    r, g, b = bytes.fromhex(colour.removeprefix("#"))
    return (float(r), float(g), float(b))


def _scale(colour: RGB, f: float) -> RGB:
    return (colour[0] * f, colour[1] * f, colour[2] * f)


def _mix(a: RGB, b: RGB, f: float) -> RGB:
    return (
        a[0] + (b[0] - a[0]) * f,
        a[1] + (b[1] - a[1]) * f,
        a[2] + (b[2] - a[2]) * f,
    )


def _period(speed: int, slow_s: float, fast_s: float) -> float:
    return slow_s + (fast_s - slow_s) * speed / PERCENT


def _around(colours: list[str], turns: float) -> RGB:
    """The colour `turns` of the way round a loop through the colours, eased
    from one to the next; round the rainbow from the colour when only one."""
    if len(colours) == 1:
        hue, _, _ = colorsys.rgb_to_hsv(*(c / 255 for c in rgb(colours[0])))
        r, g, b = colorsys.hsv_to_rgb((hue + turns) % 1, 1, 1)
        return (r * 255, g * 255, b * 255)
    pos = turns % 1 * len(colours)
    f = pos - int(pos)
    i = int(pos) % len(colours)  # float % can give 1.0 just below a whole turn
    ease = f * f * (3 - 2 * f)
    return _mix(rgb(colours[i]), rgb(colours[(i + 1) % len(colours)]), ease)


def _flash(lights: Lights, t: float, part: int) -> RGB:
    """Lightning: one flash at a random moment of each interval, fading out."""
    interval = _period(lights.speed, *LIGHTNING_INTERVAL_S)
    n = int(t // interval)
    # the same interval always gets the same flash: no state between frames
    digest = hashlib.blake2b(f"{n}:{part}".encode(), digest_size=8).digest()
    at = digest[0] / 256 * interval * LIGHTNING_SPREAD
    colour = rgb(lights.colours[digest[1] % len(lights.colours)])
    since = t - n * interval - at
    return _scale(colour, math.exp(-since / LIGHTNING_FADE_S)) if since >= 0 else BLACK


def parts_at(lights: Lights, t: float, status: Status) -> tuple[RGB, RGB]:
    """The top and bottom colours at t seconds."""
    top, bottom = rgb(lights.top), rgb(lights.bottom)
    match lights.effect:
        case "solid":
            return top, bottom
        case "voice":
            f = VOICE_FLOOR + (1 - VOICE_FLOOR) * status.level
            return _scale(top, f), _scale(bottom, f)
        case "pulse":
            period = _period(lights.speed, *PULSE_PERIOD_S)
            n = int(t // period)
            f = (1 - math.cos(2 * math.pi * (t / period - n))) / 2
            colour = _scale(rgb(lights.colours[n % len(lights.colours)]), f)
            return colour, colour
        case "cycle":
            colour = _around(lights.colours, t / _period(lights.speed, *CYCLE_PERIOD_S))
            return colour, colour
        case "wave":
            turns = t / _period(lights.speed, *CYCLE_PERIOD_S)
            return _around(lights.colours, turns - WAVE_LAG), _around(
                lights.colours, turns
            )
        case "blink":
            n = int(t // (_period(lights.speed, *BLINK_PERIOD_S) / 2))
            if len(lights.colours) == 1:
                colour = rgb(lights.colours[0]) if n % 2 == 0 else BLACK
            else:
                colour = rgb(lights.colours[n % len(lights.colours)])
            return colour, colour
        case "lightning":
            return _flash(lights, t, 0), _flash(lights, t, 1)


def load() -> Lights:
    try:
        data: object = json.loads(SETTINGS_FILE.read_text())
    except OSError, ValueError:
        return Lights()
    match parse_lights(data):
        case ParseError():
            return Lights()
        case lights:
            return lights


def _systemctl(*args: str) -> LightsError | None:
    error = systemctl(*args)
    return LightsError(error) if error else None


def apply(lights: Lights, *, switched: bool) -> LightsError | None:
    """Save the settings; the running daemon picks up a colour change itself.
    switched: turned on or off, so the unit (rewritten if stale) starts or
    stops. Only then does it run systemctl, which the popup does off the main
    thread."""
    try:
        _ = replace_text(SETTINGS_FILE, json.dumps(asdict(lights), indent=2) + "\n")
        if not switched:
            return None
        unit_changed = replace_text(UNIT_FILE, UNIT_TEXT)
    except OSError as e:
        return LightsError(str(e))
    if unit_changed and (err := _systemctl("daemon-reload")):
        return err
    if not lights.on:
        return _systemctl("disable", "--now", UNIT)
    return _systemctl("enable", UNIT) or _systemctl("restart", UNIT)
