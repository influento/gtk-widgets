"""Voice processing: an echo-cancelled copy of one mic for calls.

PipeWire's echo-cancel module (WebRTC), then an optional neural noise filter
(a LADSPA plugin in a filter-chain), run in a pipewire process of its own
under a user unit, so it is back after a reboot and a settings change restarts
only it (about 1 s without that mic). It takes the echo reference from the
default output's monitor (monitor.mode), so playback is not routed through it.
The settings file is the truth: the conf and the unit are written from it and
never read back. Turning it on or off points PipeWire's configured default
source at the echo-cancelled mic or back at the mic, by name: WirePlumber
switches once the node appears, so the popup may close at once.
"""

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.widgets.audio.parse import NoiseFilter, Voice, parse_voice

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
SETTINGS_FILE = CONFIG_HOME / "gtk-widgets" / "audio-voice.json"
CONF_FILE = CONFIG_HOME / "gtk-widgets" / "echo-cancel.conf"
UNIT = "gtk-widgets-echo-cancel.service"
UNIT_FILE = CONFIG_HOME / "systemd" / "user" / UNIT
SOURCE_NAME = "gtk_widgets_echo_cancel"  # node name of the echo-cancelled mic
PIPEWIRE = "/usr/bin/pipewire"
SYSTEMCTL_TIMEOUT_S = 15
LADSPA_DIR = Path("/usr/lib/ladspa")


@dataclass(frozen=True, slots=True)
class Control:
    """One control port of a filter plugin, as the popup shows it."""

    key: str  # in Voice.controls
    port: str  # the plugin's port name
    label: str
    tip: str
    low: float
    high: float
    step: float
    default: float
    unit: str


@dataclass(frozen=True, slots=True)
class Plugin:
    name: str
    file: Path
    label: str  # LADSPA label of its mono plugin
    package: str
    controls: tuple[Control, ...]


FILTER_NAMES: dict[NoiseFilter, str] = {
    "off": "Off",
    "rnnoise": "RNNoise",
    "deepfilter": "DeepFilterNet",
}
# Defaults: RNNoise's as its author documents them (the LADSPA hints are
# coarser); DeepFilterNet's plugin defaults but the minimum threshold and the
# post filter, tuned on a typing + speech take (10 dB: typing silent, voice
# kept; 15 dipped the voice, 20 cut it)
PLUGINS: dict[NoiseFilter, Plugin] = {
    "rnnoise": Plugin(
        "RNNoise",
        LADSPA_DIR / "librnnoise_ladspa.so",
        "noise_suppressor_mono",
        "noise-suppression-for-voice",
        (
            Control(
                "rnnoise.vad_threshold",
                "VAD Threshold (%)",
                "Voice threshold",
                "How sure it must be that you are speaking before it lets sound "
                "through; lower keeps soft speech and laughs, higher cuts more noise",
                0,
                99,
                1,
                50,
                "%",
            ),
            Control(
                "rnnoise.vad_grace",
                "VAD Grace Period (ms)",
                "Hold after speech",
                "Sound stays on this long after speech, so word endings are kept",
                0,
                1000,
                10,
                200,
                "ms",
            ),
            Control(
                "rnnoise.retroactive_grace",
                "Retroactive VAD Grace (ms)",
                "Hold before speech",
                "Sound from this long before speech is let through, so word starts "
                "are kept; delays the mic by as much",
                0,
                200,
                10,
                0,
                "ms",
            ),
            Control(
                "rnnoise.dry_mix",
                "Dry Mix",
                "Original mixed in",
                "How much of the unfiltered sound is mixed back in",
                0,
                1,
                0.05,
                0,
                "",
            ),
        ),
    ),
    "deepfilter": Plugin(
        "DeepFilterNet",
        LADSPA_DIR / "libdeep_filter_ladspa.so",
        "deep_filter_mono",
        "deepfilternet-ladspa",
        (
            Control(
                "deepfilter.attenuation_limit",
                "Attenuation Limit (dB)",
                "Attenuation limit",
                "The most it lowers noise; lower leaves some room sound",
                0,
                100,
                1,
                100,
                "dB",
            ),
            Control(
                "deepfilter.min_threshold",
                "Min processing threshold (dB)",
                "Noise threshold",
                "Moments whose voice-to-noise level is below this are silenced as "
                "noise; too high cuts your voice",
                -15,
                35,
                1,
                10,
                "dB",
            ),
            Control(
                "deepfilter.max_erb_threshold",
                "Max ERB processing threshold (dB)",
                "Coarse stage limit",
                "Above this voice-to-noise level the coarse (ERB) stage leaves the "
                "sound alone",
                -15,
                35,
                1,
                35,
                "dB",
            ),
            Control(
                "deepfilter.max_df_threshold",
                "Max DF processing threshold (dB)",
                "Fine stage limit",
                "Above this voice-to-noise level the fine (deep filter) stage "
                "leaves the sound alone",
                -15,
                35,
                1,
                35,
                "dB",
            ),
            Control(
                "deepfilter.min_buffer",
                "Min Processing Buffer (frames)",
                "Processing buffer",
                "The plugin's minimum processing buffer, in 10 ms frames",
                0,
                10,
                1,
                0,
                "",
            ),
            Control(
                "deepfilter.post_filter",
                "Post Filter Beta",
                "Post filter",
                "Extra cleanup of noise left between words",
                0,
                0.05,
                0.005,
                0.02,
                "",
            ),
        ),
    ),
}

# After/BindsTo as PipeWire's own filter-chain.service; wanted by pipewire.service,
# so a restarted or socket-activated PipeWire brings it up again
UNIT_TEXT = f"""[Unit]
Description=gtk-widgets echo-cancelled microphone
After=pipewire.service pipewire-session-manager.service
BindsTo=pipewire.service

[Service]
Type=simple
ExecStart={PIPEWIRE} -c {CONF_FILE}
Restart=on-failure
Slice=session.slice

[Install]
WantedBy=pipewire.service
"""


class VoiceError(RuntimeError):
    """A settings file, conf or unit that could not be written, a failed
    systemctl, or a noise filter that is not installed."""


def value(voice: Voice, control: Control) -> float:
    """The control's setting, within its range."""
    v = voice.controls.get(control.key, control.default)
    return min(max(v, control.low), control.high)


def load() -> Voice:
    try:
        data: object = json.loads(SETTINGS_FILE.read_text())
    except OSError, ValueError:
        return Voice()
    match parse_voice(data):
        case ParseError():
            return Voice()
        case voice:
            return voice


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _flag(*, on: bool) -> str:
    return "true" if on else "false"


def _filter_chain(plugin: Plugin, voice: Voice, description: str) -> str:
    controls = "\n".join(
        f"                  {_quote(c.port)} = {value(voice, c):g}"
        for c in plugin.controls
    )
    return f"""
    {{ name = libpipewire-module-filter-chain
      args = {{
        node.description = {_quote(f"{plugin.name} noise filter")}
        media.name = {_quote(f"{plugin.name} noise filter")}
        filter.graph = {{
          nodes = [
            {{
              type = ladspa
              name = filter
              plugin = {_quote(str(plugin.file))}
              label = {plugin.label}
              control = {{
{controls}
              }}
            }}
          ]
        }}
        audio.rate = 48000
        audio.channels = 1
        audio.position = [ MONO ]
        capture.props = {{
          node.name = "{SOURCE_NAME}.filter"
          target.object = "{SOURCE_NAME}.unfiltered"
          node.passive = true
          node.dont-fallback = true
        }}
        playback.props = {{
          node.name = "{SOURCE_NAME}"
          media.class = Audio/Source
          node.description = {_quote(f"Echo-cancelled {description}")}
        }}
      }}
    }}"""


def conf_text(voice: Voice, mic: str, description: str) -> str:
    plugin = PLUGINS.get(voice.noise_filter)
    # with a plugin, the echo canceller's output is its input
    aec_name = f"{SOURCE_NAME}.unfiltered" if plugin else SOURCE_NAME
    aec_description = f"Echo-cancelled {description}" + (
        " (unfiltered)" if plugin else ""
    )
    return f"""context.properties = {{ log.level = 0 }}
context.spa-libs = {{
    audio.convert.* = audioconvert/libspa-audioconvert
    support.*       = support/libspa-support
}}
context.modules = [
    {{ name = libpipewire-module-rt args = {{ }} flags = [ ifexists nofail ] }}
    {{ name = libpipewire-module-protocol-native }}
    {{ name = libpipewire-module-client-node }}
    {{ name = libpipewire-module-adapter }}
    {{ name = libpipewire-module-echo-cancel
      args = {{
        library.name = aec/libspa-aec-webrtc
        monitor.mode = true
        aec.args = {{
          # its noise suppression left typing almost as loud (measured)
          webrtc.noise_suppression = false
          webrtc.gain_control = {_flag(on=voice.gain_control)}
          webrtc.high_pass_filter = {_flag(on=voice.high_pass_filter)}
          # transient_suppression stays off: it acts only on key presses the
          # app reports, and PipeWire reports none (measured: no effect)
          webrtc.transient_suppression = false
        }}
        capture.props = {{
          node.name = "{SOURCE_NAME}.capture"
          target.object = {_quote(mic)}
          node.passive = true
          # else a missing mic falls back to the default one, which can be
          # this source itself
          node.dont-fallback = true
        }}
        sink.props = {{
          node.name = "{SOURCE_NAME}.reference"
        }}
        source.props = {{
          node.name = "{aec_name}"
          node.description = {_quote(aec_description)}
        }}
      }}
    }}{_filter_chain(plugin, voice, description) if plugin else ""}
]
"""


def _write(path: Path, text: str) -> bool:
    """Write text atomically; False when the file already held it."""
    try:
        if path.read_text() == text:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    _ = tmp.write_text(text)
    _ = tmp.replace(path)
    return True


def _run(*argv: str) -> VoiceError | None:
    try:
        done = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=SYSTEMCTL_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return VoiceError(f"{' '.join(argv)}: {e}")
    if done.returncode:
        return VoiceError(
            done.stderr.strip() or f"{' '.join(argv)}: exit {done.returncode}"
        )
    return None


def _systemctl(*args: str) -> VoiceError | None:
    return _run("systemctl", "--user", *args)


def _default_source(name: str) -> VoiceError | None:
    value = json.dumps({"name": name})
    return _run(
        "pw-metadata", "-n", "default", "0", "default.configured.audio.source", value
    )


def apply(
    voice: Voice, description: str, *, restart: bool, switched: bool
) -> VoiceError | None:
    """Save the settings; with restart, (re)start the unit with them or stop it.
    switched: turned on or off, so the default source follows."""
    try:
        _ = _write(SETTINGS_FILE, json.dumps(asdict(voice), indent=2) + "\n")
        if not restart:
            return None
        plugin = PLUGINS.get(voice.noise_filter)
        if voice.on and plugin and not plugin.file.exists():
            return VoiceError(
                f"{plugin.name} is not installed: sudo pacman -S {plugin.package}"
            )
        if voice.on and voice.mic is not None:
            _ = _write(CONF_FILE, conf_text(voice, voice.mic, description))
        unit_changed = _write(UNIT_FILE, UNIT_TEXT)
    except OSError as e:
        return VoiceError(str(e))
    if unit_changed and (err := _systemctl("daemon-reload")):
        return err
    if not (voice.on and voice.mic is not None):
        if switched and voice.mic is not None and (err := _default_source(voice.mic)):
            return err
        return _systemctl("disable", "--now", UNIT)
    if switched and (err := _default_source(SOURCE_NAME)):
        return err
    return _systemctl("enable", UNIT) or _systemctl("restart", UNIT)
