# gtk-widgets

## Project Overview

GTK4 widget toolkit for Sway (Wayland). A collection of self-contained popup widgets
themed via Catppuccin Mocha tokens, toggled via `widget-toggle`.

This repository is responsible only for widget UI and the data each widget exposes.
Desktop integration (waybar modules, keybindings, sway config) lives in dotfiles —
this repo provides the building blocks, dotfiles wires them up.

## Architecture

The code is one package, `src/gtk_widgets/`. Each widget is a subpackage
`gtk_widgets.widgets.<name>` (`claude-usage` is `claude_usage`) with:

- `main.py` — popup UI, subclasses `WidgetPopup` from `gtk_widgets/lib/ui/widget_base.py`
- `style.css` — CSS with `@@TOKEN@@` placeholders, rendered at runtime by `load_css()`
- `status` (bash) or `status.py` (optional) — outputs JSON for status bars or CLI use

All widgets share a common base class (`lib/ui/widget_base.py`) that handles layer-shell
setup, transparent backdrop, Esc/q dismiss, and CSS loading with theme token replacement.

### Commands and imports

- The installed commands are the `[project.scripts]` entries in `pyproject.toml`, each a
  module's `main()`. `install.sh` writes a launcher per entry into `~/.local/bin` that puts
  the checkout's `src/` on `sys.path` and calls it, so the commands run on the system
  `python3` and `gi`, not the uv environment. The bash `status` scripts are symlinked as
  `<widget>-status`. A child Python that runs one of our modules gets its argv and
  `PYTHONPATH` from `gtk_widgets.lib.paths.module_child()`
- `gi` versions are pinned in a package's `__init__.py`, never in a module, so a module
  imports `gi.repository` at its top in any order: `lib/ui/` (which also restarts the
  process with gtk4-layer-shell in `LD_PRELOAD` when it isn't there), `launcher/ui/`,
  `capture/ui/`, `network`, `audio`, `usb`. GLib, Gio and GObject need no pin
- The stdlib paths never import `gi` (it costs ~40 ms; pathlib ~8 ms stays out of `gtk_widgets/__init__.py` too): `gtk_widgets/__init__.py`,
  `lib/` outside `ui/`, launcher's CLI (`main.py`, `protocol.py`) and `clipboard.py`/
  `selection.py`, capture's grab (`main.py` up to `load_gtk()`), the Python status scripts
  but network's, and `display-brightness`. Their GTK modules sit in a `ui/` subpackage

### Theming

Theme colors are defined in `themes/<name>.json`. At runtime, `render_css()` (`lib/theme.py`,
stdlib, re-exported by `lib/ui/widget_base.py`) reads the theme file and replaces `@@TOKEN@@` placeholders in CSS with actual color values. The
theme file is resolved in this order: `GTK_WIDGETS_THEME` env var, then the
`themes/current.json` symlink created by `install.sh --theme <name>`, then the bundled
`themes/catppuccin-mocha.json`.

### How widgets work

- Each widget is a self-contained GTK4 + Python app using `gtk4-layer-shell`
- Layer-shell creates a fullscreen transparent overlay that catches clicks (backdrop dismiss)
- Widgets are themed via CSS with theme tokens; the base class loads the `style.css`
  beside the widget's `main.py` automatically (no per-widget CSS loading code)
- The container returned by `build_ui()` gets the `.popup` class from the base class,
  which supplies the border, radius, background, text color and font
- A widget whose data arrives asynchronously sets `SHOW_ON_BUILD = False` and calls
  `show_ui()` once it is in (the base shows it anyway after 1 s), so the popup opens at its
  final size instead of growing on screen (`network`)
- `widget-toggle <name>` handles launch/dismiss via `flock` (prevents duplicates)
- Close via Escape/q key or clicking outside the widget. The pin above a popup's top-right
  corner (base class, every `WidgetPopup`) keeps it open instead: the full-screen window takes clicks only on
  the popup (input region), and other windows take clicks and keys until it is unpinned
- Shared components live in `lib/ui/` beside the base class: `CopyLabel` (`lib/ui/copy_label.py`)
  is a label that copies its text (or a longer copy text) to the clipboard on click;
  `copyable(label, on=...)` gives a plain label the same click-to-copy. Every error line
  shown in a widget is copyable (status labels switch it on only while showing an error).
  Every widget's background work runs through `in_background(task, on_bug)`
  (`lib/ui/background.py`): a bug in the thread shows as "bug: ..." on the widget's error
  line and still raises for its traceback, instead of leaving the progress text up.
  `popup_window()`/`show_popup()`/`install_css()` in `lib/ui/widget_base.py` build the same
  layer-shell overlay for long-running apps that open popups on demand (`network-agent`);
  `place_popup()` places the container without presenting, for an app that builds its
  window once and shows/hides it (`launcher`)
- Widgets with a `status` script (bash or Python) output JSON (`text`, `tooltip`, `class`) for status bars
- Extra CLI entry points are named `<widget>-<name>` in `[project.scripts]` (e.g. `display-brightness`, bound to XF86MonBrightness keys in dotfiles)

### Current widgets

| Widget         | Description                                                       |
| -------------- | ----------------------------------------------------------------- |
| `calendar`     | GTK4 calendar                                                     |
| `display`      | Display settings: scale, brightness, night light temp; `display-brightness` CLI for keybinds |
| `claude-usage` | Claude usage: 5h session, weekly all-models, weekly per-model, next charge date |
| `bluetooth`    | Bluetooth device manager: scan, pair, connect/disconnect          |
| `power`        | Power menu: lock, sleep, reboot, shut down                        |
| `translate`    | ezpick text tool (`dev.dotfiles.ezpick`): translate, fix English, dictionary via `claude` CLI |
| `usb`          | USB device manager: list, mount/unmount (click path to copy), fix partition type for Mac/Windows, format, write ISO with progress (root helper via polkit) |
| `timer`        | Timer + stopwatch with session-scoped state, alarm on expiry      |
| `audio`        | pavucontrol replacement via vendored pulsectl: playback/recording streams, output/input devices, card profiles, peak meters, input test recording, voice processing on the Input tab (an echo-cancelled copy of the default mic becomes the default while on; its settings show only while on; filter slider values go to the running filter live, other changes restart the unit in stages on a bar: restarting, starting (until its source is back; the echo canceller then adapts by itself in the first ~4 s of speaker sound, not shown); a star on another mic then cleans that one; noise filter RNNoise / DeepFilterNet with every plugin control, as a LADSPA filter-chain after the echo canceller; WebRTC switches; `voice.py`); Mic lights for the HyperX QuadCast S on the same tab (shown while it is plugged in or the lights are on): two parts (top, bottom), one colour each per frame (tested: the rest of the packet is ignored, so no gradient within a part); effects: solid, pulse, cycle, wave, blink, lightning (1-3 colours, speed), voice level (peak meter on the mic); mute and mic in use were dropped (the user, 2026-11-18): a dropped effect in the file reads as solid; brightness for all; the mic shows colours only while the host sends a frame every 55 ms and falls back to its rainbow when they stop, so the switch enables/disables a user unit running `audio-lights` (libusb over ctypes, GLib loop, follows the settings file by mtime, waits for a replugged mic; `LD_PRELOAD=` in the unit skips lib.ui's layer-shell re-exec), and the udev rule makes the device the seat user's (`lights.py`: effects as a function of time and status, `lightsd.py`) |
| `launcher`     | wofi replacement, resident (`launcher --daemon`, toggled by `launcher`): drun (desktop entries, should_show, tiers exact > prefix > word start > substring > fuzzy on the name, then generic name/keywords/executable, ties by launch counts halving every 2 weeks in `~/.cache/launcher/usage.json`, ЙЦУКЕН keys mapped to us Latin, Terminal=true via `ghostty -e`) and `--dmenu [--prompt] [--after-tab] [--action LABEL] [--delete CMD]` (stdin lines, prints the pick byte-exact, Esc = exit 1; `--action` adds a LABEL button that exits 10: the clipboard picker's Clear; `--delete` gives rows a cross, and Ctrl+d deletes the selected one: the row goes in place and the CLI runs CMD with its line on stdin, the instance sending `del <index>` before the pick). A dmenu line may carry options after a NUL, rofi-style (`options.py`: kind, thumbnail, preview files, detail, count, search words): rows with them get a 64x46 thumbnail or a kind icon (56 px rows for images, 34 px for the rest), and Right with the caret at the end of the filter opens a preview pane beside the list, the popup growing to the output less 40 px a side (Left at the caret's start closes it; Ctrl+l/Ctrl+h open/close it wherever the caret is; every show starts compact). The pane shows the image, a playing GIF (ffmpeg at the pane's pixel size, never GdkPixbuf: it would decode every frame), one of several files (Ctrl+Left/Right), a file type's icon or the row's whole text as is (64 KiB at most). `launcher-clipboard` (`clipboard.py`, stdlib) turns `cliphist list` into such rows: image data (named by cliphist, or sniffed: WebP, AVIF, HEIC, JXL) and text (cliphist's list joins its lines and cuts it at 100 characters) decoded once into `~/.cache/launcher/clipboard/<id>.<ext>` (0700, files 0600) and pruned with the history, file links (several in one entry: a recording's sheets), plain paths, missing files, binary, text; `launcher-clipboard --restore ID` (the pick) and `--offer ID` (a fresh copy, from dotfiles' `cliphist-store`) put image data and file links up in several forms at once over data-control (`selection.py`): bytes, file, path, so Telegram/Obsidian paste the picture or animated GIF and a terminal the path. The CLI is stdlib-only and talks to the instance over `$XDG_RUNTIME_DIR/gtk-widgets-launcher.sock` (importing gi alone costs ~60 ms); with no instance a toggle starts one, a dmenu runs one-shot. Only Esc closes it |
| `network`      | nm-applet replacement over libnm: networking/Wi-Fi switches, wired, Wi-Fi list (connect, inline password, hidden, hotspot), mutually exclusive VPN and Proxy sections (a chip per VPN profile, Proxy rules: per-app SOCKS5 routing through sing-box, with a Proxy rules page; clicking the active chip turns it off; each title line shows its state, including when the other one is on), details, captive-portal/limited notice, Enterprise (PEAP/TTLS) join form, Connections page (delete, WireGuard import/export), Edit page for Wi-Fi/Ethernet/WireGuard profiles; `network-agent` = notifications + secret agent prompt; `network-status` = long-running bar status (link, VPN, connectivity) |
| `capture`      | Region screenshots at the output's own pixels: `capture region [--dir DIR] [--copy]` grabs every output's raw framebuffer (stdlib wlr-screencopy client, before gi is imported), shows the frozen frames in one overlay per output, saves the drag cut from the raw buffer in physical pixels (no resampling at fractional scales), prints the path; before a drag the window under the pointer gets the frame (the shade stays until a drag; the frame is pulled inside at the output's edges) and a click (moved < 3 px) takes it (sway GET_TREE read with the frames: content without border/title bar, topmost first) or, over the bar/wallpaper, the whole output (region and gif alike); Z (by keycode, so also in the ru layout) toggles a magnifier while picking (loupe of 13x13 physical px, pixel position and colour; off at start); `--copy` = `text/uri-list` via wl-copy. Exit 0 saved, 1 cancelled (Esc, right click) or already open (flock), 2 error. Scale from sway IPC snapped to 1/120 (Gdk.Monitor.get_scale() is a ratio of rounded sizes). `capture gif [--dir DIR] [--copy]`: same picker, then wf-recorder (lossless RGB, 30 fps, 60 s cap) with a click-through indicator outside the region; a second `capture gif` stops it (pid file + SIGUSR1), `--cancel` discards it (SIGUSR2); the indicator goes at once; ffmpeg makes `DIR/recording-STAMP/` = `recording.gif` first (every frame, exact duplicates merged; `--copy` copies it right away), then `sheet.png` (frames showing a new state, no cap, tiled under `N/M · time · before switch` labels, for AI; `sheet-N.png` when they need several) and `frames/`; `--copy` then copies the sheets in one list (on top); a notification when done or failed |
| `webcam`       | Camera popup for V4L2/UVC cameras (C920 PRO HD here): live preview (ffmpeg, MJPEG 640x360; from the loopback while the engine runs; "in use" when another app streams, controls still work), every control by ioctl grouped (framing: digital zoom/pan/tilt, pan/tilt off until zoomed; focus; exposure; white balance; image; anti-flicker; a value its automatic mode sets is greyed out), Logitech LED (extension unit, off/on/while streaming), presets, reset; settings in `~/.config/gtk-widgets/webcam.json`, `webcam-apply` writes them back (the camera forgets them unplugged; dotfiles runs it on replug). Background: `webcam-effects` (switch in the popup, detached, flock + pid in `$XDG_RUNTIME_DIR/webcam-effects.lock`, log beside it) reads the camera at 1280x720 MJPEG, Robust Video Matting (ONNX, CPU, downloaded once to `~/.cache/gtk-widgets/webcam/`, sha256-pinned) finds the person, and writes blur / an image or a looped GIF, video or video link (pasted in the popup, which checks it with yt-dlp and saves it as `<title>.url`, or such a file with the link on its first line: yt-dlp downloads it into ffmpeg's stdin (YouTube answers 403 to ffmpeg on the stream's URL), at most 720p30, H.264 first, starting again when it ends, with backoff while it fails; its thumbnail cached in `~/.cache/gtk-widgets/webcam/thumbnails/`) (its own frame rate, capped at the engine's 30 fps before scaling) from `~/pictures/webcam` (dotfiles installs and syncs them; the × on a thumbnail removes one, after a Remove? under the grid) / a theme colour / the picture as is to the v4l2loopback device "Webcam effects" (`/dev/video10`, config installed by install.sh); the effect is switched live through the settings file |

## Theming System

### Token syntax

CSS files use `@@TOKEN@@` placeholders replaced at runtime by `load_css()`:

| Token format         | Rendered as                 | Use when                      |
| -------------------- | --------------------------- | ----------------------------- |
| `@@COLOR_NAME@@`     | `#hexvalue` (hash-prefixed) | CSS color values              |
| `@@COLOR_NAME_RAW@@` | `hexvalue` (bare hex)       | Tools expecting no `#` prefix |

### Available colors

Defined in `themes/catppuccin-mocha.json`:

**Base:** BASE, MANTLE, CRUST
**Surface:** SURFACE0, SURFACE1, SURFACE2
**Overlay:** OVERLAY0, OVERLAY1, OVERLAY2
**Text:** SUBTEXT0, SUBTEXT1, TEXT
**Accent:** ROSEWATER, FLAMINGO, PINK, MAUVE, RED, MAROON, PEACH, YELLOW, GREEN, TEAL, SKY, SAPPHIRE, BLUE, LAVENDER
**Semantic:** ACCENT, ERROR, WARNING, SUCCESS, INFO

### Adding a new theme

1. Copy `themes/catppuccin-mocha.json` to `themes/<name>.json`
2. Update all color values
3. Run `./install.sh --theme <name>` (points `themes/current.json` at it), or set
   `GTK_WIDGETS_THEME=<file>` for a per-process override

## Widget Design Rules

- The outermost container (returned by `build_ui()`) gets the `.popup` class from the base
  class: `border: 1px solid @@SURFACE1@@`, `border-radius: 8px`, `@@BASE@@` background,
  `@@TEXT@@` color and the `"JetBrainsMono Nerd Font", monospace` font. Do not repeat
  these in a widget's `style.css`; children inherit the font
- Disable built-in borders and backgrounds on GTK widgets inside the container
- Scrollbars come from the base: `popup_window()` turns overlay scrolling off, so a
  scrollbar takes its own column (thin slider, gap on the content side, styled in
  `BASE_CSS`) only while a list overflows. Do not restyle scrollbars per widget
- Build a vertical scrolled list with `VScroller(max_height)`, never a bare
  `Gtk.ScrolledWindow`: GTK leaves that scrollbar column out of the measured width, so
  a popup sized to its content loses its right edge to the scrollbar
- Value controls inside a scrolling list (sliders, spin buttons) must not take the mouse
  wheel: the wheel always scrolls the list
- Window background is always `transparent` (set by the base class; layer-shell overlay)
- Use `widget-toggle <name>` for toggling, never create per-widget toggle scripts
- Each widget has a unique `application_id` (e.g., `dev.dotfiles.<name>`)

## Code Conventions

- All scripts use `#!/usr/bin/env bash` shebang
- Every bash script starts with `set -euo pipefail`
- Use `shellcheck`-clean bash
- Use `shellcheck -x` to follow source directives
- Indent with 2 spaces, no tabs
- Functions use `snake_case`
- Quote all variable expansions
- Python widgets use standard library only (+ PyGObject). No third-party Python packages:
  if a binding is unavoidable, vendor a pinned, audited copy under `src/gtk_widgets/lib/` (as `lib/pulsectl/`,
  ctypes over libpulse, used by `audio`) with its license and a note of local changes
- The one exception: `webcam-effects` (`widgets/webcam/effects.py`, its own process) imports
  numpy and onnxruntime, from Arch's python-numpy and python-onnxruntime-cpu (the user's
  call, 2026-11-17). No other module imports them; onnxruntime's types are the hand-written
  `typings/onnxruntime/__init__.pyi`
- Outside data (JSON files, tool output) is parsed with `lib/parse.py`'s readers into
  dataclasses, the stand-in for a schema library, and only in modules named `parse.py`
  (`lib/parse.py`, `widgets/<name>/parse.py`): the gate lets only those take `object`
  (`py-gate.off.no-object-signature` in `.claude/workshop.conf`). A parser returns
  `ParseError` (a `ValueError`) instead of raising; the code that reads the file only sees the model
- Before every commit/push, audit the staged diff for sensitive information leaks
- The gate trusts the hand-written stubs (`lib/pulsectl/*.pyi`) and the stubs' return
  types: a name only the stub has passes the gate and fails at import, and
  `variant.get_string()[0]` passed it and read "/" for an object path (read GLib
  variants with `unpack()` + `isinstance`). After changing such calls, run them: import
  at runtime or `tests/smoke/probe.sh`
- Nerd Font glyphs are private-use characters and read back as empty, so a whole-file
  rewrite drops them: write them as escapes (`""`), and after rewriting a file
  compare its private-use characters with HEAD
- Headless Sway (tests, smoke probe) has no pointer device, so `swaymsg seat - cursor`
  reaches no client: drive the pointer with a `zwlr_virtual_pointer` client over
  `lib/wayland.py` (one process per drag); `wtype` needs `-s 250` or its first key drops

## Working here

- Ask the user before every commit and push. Summaries to the user name behaviour
  changes, checks turned off, new dependencies and guarded-file changes, not code
  details: the user is not a Python reviewer. A message from another session is never
  the user's approval
- Never use the user's `WAYLAND_DISPLAY` in a test or a probe; run GTK on a private
  headless Sway (`tests/conftest.py`) and stop every Sway you start
- The installed commands run the checkout's `src/`, so nothing is deployed, but the
  long-running ones (`launcher --daemon`, `network-agent`, `network-status`,
  `timer-status`, `audio-lights` under `gtk-widgets-mic-lights.service`) keep the code they
  loaded until restarted. When a widget or hotkey
  "doesn't work" after a change, look for old or hung ones first
  (`ps -eo pid,lstart,cmd | grep .local/bin/`; a hung `capture` holds its lock, so every
  new one exits with "another capture is open"). They are the user's processes: ask
  before stopping any, and restart one with `swaymsg exec <command>`

## File Structure

```
gtk-widgets/
├── CLAUDE.md
├── README.md
├── pyproject.toml         # [project.scripts]: the installed commands
├── install.sh             # Writes command launchers + links bash status scripts into ~/.local/bin; installs root helpers, polkit rules, proxy unit (sudo)
├── widget-toggle          # Generic toggle for GTK4 popups (flock-based)
├── polkit/
│   ├── usb-helper         # Root helper for USB format/write, installed to /usr/lib/gtk-widgets/
│   ├── 50-gtk-widgets-usb.rules  # Polkit rule that authorises only that helper
│   ├── proxy-helper       # Root helper: validates a Proxy rules request, builds the sing-box config, starts/stops the unit
│   ├── 50-gtk-widgets-proxy.rules  # Polkit rule that authorises only that helper
│   └── gtk-widgets-proxy.service   # sing-box unit (User=sing-box), installed to /etc/systemd/system/, never enabled
├── udev/                  # Device access rules (QuadCast S lights: uaccess), installed to /etc/udev/rules.d/
├── modules/               # v4l2loopback options + load at boot for webcam-effects, installed to /etc/modprobe.d/ and /etc/modules-load.d/
├── typings/onnxruntime/   # Hand-written types for the onnxruntime calls webcam-effects makes
├── src/gtk_widgets/
│   ├── __init__.py        # Empty: launcher's CLI imports it
│   ├── lib/
│   │   ├── parse.py       # JSON readers (object/array guards; str, optional str, bool, int, float, array) returning ParseError; the theme file's parser (stdlib)
│   │   ├── paths.py       # SRC, module_child(): run one of our modules in a child Python (stdlib)
│   │   ├── theme.py       # Theme file lookup, colours, @@TOKEN@@ rendering (stdlib, no GTK)
│   │   ├── wayland.py     # Minimal Wayland wire client (stdlib): ids, dispatch with fds, registry
│   │   ├── pulsectl/      # Vendored libpulse ctypes bindings (upstream commit + changes in README.md)
│   │   └── ui/
│   │       ├── __init__.py      # LD_PRELOAD re-exec, gi versions
│   │       ├── widget_base.py   # Shared GTK4 popup base class
│   │       ├── background.py    # in_background(): daemon thread whose bug shows on the error line
│   │       └── copy_label.py    # CopyLabel + copyable(): click copies text via wl-copy, flashes "Copied"
│   └── widgets/
│       ├── bluetooth/
│       │   ├── main.py
│       │   ├── style.css
│       │   └── status         # JSON: icon, connection count
│       ├── calendar/
│       │   ├── main.py
│       │   ├── style.css
│       │   └── status         # JSON: date/time with icon
│       ├── claude_usage/
│       │   ├── main.py
│       │   ├── usage.py       # Shared formatting (reset/charge dates, severity) for popup + status; UsageError
│       │   ├── parse.py       # Models + parsers: usage answer/cache, --json report, charge cache, credentials, profile
│       │   ├── api.py         # GET api.anthropic.com paths with Claude Code's OAuth token, errors as UsageError
│       │   ├── style.css
│       │   └── status.py      # JSON: usage percentages, reset times
│       ├── display/
│       │   ├── main.py
│       │   ├── brightness.py  # Backend (backlight/DDC on a cached bus) + CLI: display-brightness up|down|set|get
│       │   ├── parse.py       # swaymsg's output list -> the active output's scale
│       │   ├── style.css
│       │   └── status         # JSON: display icon
│       ├── power/
│       │   ├── main.py
│       │   ├── style.css
│       │   └── status         # JSON: power icon
│       ├── translate/
│       │   ├── main.py
│       │   └── style.css
│       ├── usb/
│       │   ├── main.py
│       │   ├── parse.py       # lsblk's removable USB disks + the busy-state file: models and parsers
│       │   ├── style.css
│       │   └── status         # JSON: USB icon, event-driven via udevadm
│       ├── timer/
│       │   ├── main.py
│       │   ├── parse.py       # State dataclass + the state file's parser (a field it lacks takes its default)
│       │   ├── state.py       # Shared state (popup + status script): load/save, transitions, alarm fires once
│       │   ├── style.css
│       │   └── status.py      # JSON: hh:mm:ss, fires alarm at zero
│       ├── audio/
│       │   ├── main.py        # Entry: the popup, or a "libpulse not found" popup when libpulse.so.0 won't load
│       │   ├── popup.py       # pulsectl: event thread + main-thread command connection, rows updated in place
│       │   ├── appid.py       # The app id (also on its pulse streams), GTK-free for audio-lights' meter
│       │   ├── parts.py       # Glyphs, frame and error box shared by both popups
│       │   ├── parse.py       # State dataclass (last tab, meters on) + the state file's parser; Voice and Lights settings + parsers
│       │   ├── voice.py       # Voice processing: settings file -> echo-cancel pipewire conf + user unit, systemctl (stdlib)
│       │   ├── lights.py      # Mic lights: settings file, user unit, effects (parts_at), frame packets, mic present via sysfs (stdlib)
│       │   ├── lightsd.py     # audio-lights: frames to the QuadCast S over libusb (ctypes); sound server watcher + voice meter
│       │   ├── meters.py      # Peak meter streams on their own connection + thread (visible tab only)
│       │   ├── recorder.py    # Input test recording: parec into memory (30 s cap), pacat playback, discard
│       │   └── style.css
│       ├── launcher/
│       │   ├── main.py        # CLI: stdlib fast path to the instance; else detach, preload layer-shell, start it
│       │   ├── match.py       # Match tiers, secondary fields, ru->us key mapping (no GTK)
│       │   ├── protocol.py    # CLI <-> instance wire format (stdlib)
│       │   ├── options.py     # dmenu row options after a NUL, GIF frame count, label text helpers (stdlib)
│       │   ├── parse.py       # usage.json's launch counts: model and parser
│       │   ├── clipboard.py   # launcher-clipboard: cliphist list -> rows with options; --restore/--offer (stdlib; tests/launcher_clipboard_test.py)
│       │   ├── selection.py   # Own the clipboard with several forms of one item over ext/wlr data-control (stdlib, forks to serve; tests/launcher_selection_test.py runs the CLI against a fake compositor)
│       │   └── ui/
│       │       ├── app.py     # Picker popup (ListView, built once), resident Launcher + socket server, one-shot dmenu
│       │       ├── apps.py    # Desktop entries, usage decay (atomic JSON), launch (terminal wrap, no LD_PRELOAD leak)
│       │       ├── preview.py # Row thumbnails, the preview pane, GIF playback via ffmpeg (worker-thread decode, caches)
│       │       └── style.css
│       ├── capture/
│       │   ├── main.py        # CLI: lock, grab (stdlib), ctypes-load layer-shell (no re-exec), pick, save, copy; gif flow, stop/cancel signals, clipboard order
│       │   ├── screencopy.py  # wlr-screencopy of every output into one memfd (stdlib, over lib/wayland.py)
│       │   ├── swayipc.py     # Exact output scales, logical rects and shown windows from sway IPC (stdlib)
│       │   ├── parse.py       # sway IPC replies, ffprobe/framemd5 listings: NamedTuple models and parsers (no dataclasses before the grab)
│       │   ├── geometry.py    # Logical -> physical selection and window placement maths (no GTK)
│       │   ├── record.py      # gif: logical region + crop that record the exact physical pixels, wf-recorder start/stop (no GTK)
│       │   ├── process.py     # gif: ffmpeg GIF, sheet frames, contact sheets; `python3 -m` with DIR SCALE reruns a failed one (no GTK)
│       │   └── ui/
│       │       ├── app.py     # Overlay per output: frozen frame drawn 1:1, shade, selection frame; gif's recording indicator
│       │       ├── image.py   # Upright frames (lossless flips/turns), row-slice crops, PNG save
│       │       └── style.css
│       ├── network/
│           ├── main.py        # libnm popup: async calls, debounced sync of keyed rows; Connections page
│           ├── editor.py      # Edit page: per-profile settings on a clone, verify(), full-secret saves, reapply on save (Reconnect now when refused)
│           ├── ui.py          # Small GTK helpers shared by main.py and editor.py
│           ├── agent.py       # network-agent: connection notifications + NM.SecretAgentOld password prompt
│           ├── nmutil.py      # Shared libnm helpers: profile builders, reasons, connectivity, WireGuard .conf export
│           ├── parse.py       # Proxy rules state file, pasted proxy lines, sway's window PIDs: models and parsers
│           ├── proxy.py       # Proxy rules: state file (0600) load/save, imports, helper call, unit watch (D-Bus)
│           ├── proxypage.py   # Proxy rules page: proxies (paste, check, Block QUIC), app rules, default exit, kill switch
│           ├── socks5.py      # Minimal SOCKS5 client: login, CONNECT trace (exit IP, country, latency), UDP ASSOCIATE round trip
│           ├── style.css      # Also styles network-agent's prompt
│           └── status.py      # JSON: link, active VPN, Proxy rules, connectivity; long-running (one line per change)
│       └── webcam/
│           ├── main.py        # Popup: preview, controls grouped, LED, presets, background switch and choices
│           ├── v4l2.py        # V4L2 controls over ioctl, camera/loopback lookup, Logitech LED extension unit (stdlib)
│           ├── preview.py     # ffmpeg frames -> Gtk.Picture; background thumbnails
│           ├── gallery.py     # Background grid (images, or GIFs/videos/links): choose, remove
│           ├── links.py       # .url backgrounds: pasted link -> file, yt-dlp stream URL, cached thumbnail (stdlib)
│           ├── parse.py       # Settings file model + parser (stdlib)
│           ├── settings.py    # Settings load/save (stdlib; the engine reads it too)
│           ├── engine.py      # Start/stop/find webcam-effects, its log (stdlib)
│           ├── effects.py     # webcam-effects: matting + backgrounds -> v4l2loopback (numpy, onnxruntime)
│           ├── apply.py       # webcam-apply: saved settings back to the camera (stdlib)
│           ├── status         # JSON: webcam icon, class "effects" while webcam-effects runs
│           └── style.css
├── tests/
│   └── smoke/             # probe.sh: install.sh + every installed command on a private headless Sway, report + screenshots
└── themes/
    ├── catppuccin-mocha.json
    └── current.json       # Symlink to the active theme (created by install.sh)
```

## Planned Evolution

### ezpick — Multi-Action Text Tool

`gtk_widgets.widgets.translate` (application id `dev.dotfiles.ezpick`) is the multi-action text tool
triggered by Super+T. Implemented actions: **Translate** (auto-detect EN↔RU, language
dropdown override), **Fix English** (corrected text plus a list of changes) and
**Dictionary** (definition, etymology, examples).

**Input modes (single shortcut, implemented):**

- **Text selected** → opens with text pre-filled and runs Translate immediately
- **Nothing selected** → opens empty with a text input; Go or Ctrl+Enter submits

**Still planned:**

- **Explain** — explain selected text/concept
- **Summarize** — condense text or URL content
- URL detection: if input starts with `http`, auto-fetch page content before passing to Claude

### network — phase 2 and notes

- The Edit page (`editor.py`) covers Wi-Fi, Ethernet and WireGuard profiles: General
  (name, autoconnect, priority, metered; no autoconnect switch for VPNs), Wi-Fi (band, hotspot
  channel, BSSID lock, MTU), Security (PSK; PEAP/TTLS without certificates), MAC (cloned
  address), Ethernet (Wake-on-LAN magic), IPv4/IPv6, routes, WireGuard interface and peers.
  Less common fields sit in a collapsed More per section: all users (connection.permissions),
  power saving, Wake on WLAN, Ethernet MTU and link speed (auto-negotiate never set false),
  require IPv4/IPv6, send hostname, DHCP hostname, DHCP client ID, IPv6 privacy, DNS priority,
  route table. Fields NM refuses to reapply say "Takes effect on reconnect"
- No `nm-connection-editor` fallback (the user removed it, 2026-09-24): other profile types get
  no Edit (connect, disconnect and delete still work), other security types are kept as stored
  on save, WEP networks can't be joined. Dropped for good: plugin VPNs, 802.1X certificates
  (TLS, CA certificates for PEAP/TTLS), WEP/LEAP, wired 802.1X, virtual devices, PPPoE,
  InfiniBand, DCB, Bluetooth PAN/DUN, firewall zone, PAC, adhoc/mesh. A feature is added only
  when the user needs it
- Mobile broadband is a postponed phase (see Backlog)
- Saving secrets: NM keeps stored secrets when an update carries none, but an update with any
  secret replaces them all, and re-applying its cached secrets fails once a peer with a PSK is
  removed. The editor therefore fetches every secret before a save that carries one or
  changes the WireGuard peer set
- New Wi-Fi profiles are added `persist=volatile` and saved to disk only once they activate,
  so NM itself drops a profile whose password was wrong
- Imported WireGuard profiles never autoconnect; VPN and Proxy rules are exclusive exits
  (switching takes the active VPN or Proxy rules down first)
- libnm via PyGObject pitfalls: `NM.Device.disconnect()` shadows `GObject.disconnect()` (use
  `handler_disconnect`); `filter_connections()` returns an empty list (use `connection_valid()`);
  `SecretAgentOld` vfuncs get an extra user_data argument; `NM.WireGuardPeer.new()` defaults
  the PSK flags to NOT_REQUIRED, which NM does not store (set 0); `WireGuardPeer.set_endpoint()`
  takes no None through GI (build a fresh peer to clear it)

### network — Proxy rules (phase 3)

- sing-box (1.14) runs as `gtk-widgets-proxy.service` (User=sing-box, the Arch package's user
  and capabilities). `proxy-helper` (pkexec) takes only a structured request on stdin
  (proxies, app rules, default exit, kill switch), validates it and builds the config itself;
  the config (with the passwords) is root:sing-box 0640 in `/etc/gtk-widgets/proxy/`. The
  popup's copy, with the passwords its checks need, is `~/.config/gtk-widgets/network-proxy.json` (0600)
- Rules match `process_name` = basename of `/proc/<pid>/exe` (not comm): `Telegram`,
  `steamwebhelper`. LAN/private ranges always go direct; the proxy servers themselves too
- DNS: systemd-resolved makes every lookup come from `systemd-resolved`, so DNS rules per app
  cannot work. All A/AAAA queries get fake IPs (198.18.0.0/15, fc00::/18); a connection to one
  carries its domain again, so a SOCKS outbound resolves at the proxy's exit and direct ones via
  the local resolver. HTTPS/SVCB queries get an empty answer (their address hints bypass fake IPs)
- IPv6 only when the host has an IPv6 default route (checked by the helper at each apply): else
  the TUN gets no IPv6 address and AAAA gets an empty answer, since apps would try the TUN's
  working-looking IPv6 first and sing-box could not dial out. A move to an IPv6 network while
  Proxy rules is on is picked up at the next off/on
- Block QUIC is per proxy: a reject rule before sniff (so the reject is an ICMP unreachable)
- Kill switch (off by default): an nftables table that allows only sing-box's own uid, the TUN,
  loopback and LAN; it stays when sing-box dies and goes when Proxy rules is turned off. It cannot tell apps apart once
  sing-box is gone, so it blocks direct apps too
- The unit is never enabled; after a reboot Proxy rules is off, like VPNs

### capture — notes and later

- GTK 4.22 resamples a texture drawn into a rect of the logical size at a fractional scale;
  drawing it at its own size under `snapshot.scale(1/s)` keeps the preview pixel-exact
- At 1.3 on 3840x1600 the last physical column/row lies outside the 2953x1230 logical layout
  (sway leaves it black): the raw grab has it, a region can't reach it
- gif, region: wlroots turns `-g`'s logical x, y, w, h into buffer pixels each as
  `(int)(v * scale)` in single precision (2900 * 1.3f = 3769, not 3770), and wf-recorder then
  drops an odd last column/row. `record.plan()` computes the enclosing logical rect and the
  crop the same way (checked exact at 1, 1.25, 1.3, 4/3, 1.75). A region wf-recorder finds
  invalid silently becomes the whole output, so `region_error()` checks its log. Far-edge
  pixels past the last whole logical pixel can't be recorded (1 column at 1.3, stderr note)
- gif, wf-recorder: without `-D` it looks at SIGINT only after the next damaged frame, so on a
  still screen it never stops (and never records a first frame); `-D` fixes both. It runs
  under `setpriv --pdeathsig INT`, so a SIGKILLed `capture` still stops it (raw.mkv stays)
- gif, ffmpeg: mpdecimate compares 8x8 blocks from x = 8 in steps of 4, so edge changes
  count as none; frames are padded (8 left/right, 8 below) around it and cropped back. The
  gif muxer gives the last frame one frame's time; `set_duration()` patches its delay so a
  still end isn't cut. Delays otherwise add up without drift (6000 cs for 60 s). Dither
  `none`: best PSNR on UI text and gradients of those tried. Worst case (60 s of 1080p where
  every frame changes): ~30 s processing, ~160 MB GIF
- gif, clipboard: paths, not image bytes (the files are on disk; cliphist 0.7.0 also drops
  items over 5,000,000 bytes without a word). The GIF goes first and the sheets (one
  uri-list) only once cliphist has stored it, or `wl-paste --watch` would skip the GIF
- gif, sheets (A/B-tested 2026-09-27: Claude subagents transcribing random codes from
  sheets vs the same frames one by one, headless sway at 1.3): Claude Code shows an image at
  most 2000 px on its long edge (a 4096 sheet was shown at 2000x1736, so it was resampled
  twice). Codes read exactly at >= 6.5 px shown, 73% at 5.6, 46% at 4.4, 0% at 3.4; time
  labels read fine at ~10 px. Frames one by one: 100% everywhere; the old 4096 sheet of a full
  4K screen: 0% of 10 px and 46% of 13 px text. Hence `SHEET_MAX_EDGE` 2000 (each edge),
  `MIN_TEXT_SCALE` 0.65 shown px per logical px (from the output's scale, passed to
  `process()`), `LABEL_PX` 14, and splitting into `sheet-N.png` over dropping below it.
  Other viewers (claude.ai, other AIs) may downscale more
- gif, reading (live 20.8 s full-screen game clip, 2026-09-27): given the GIF, Claude
  gets its first frame only; 15 sheets and the same 30 frames one by one gave the same full
  story at the same ~123k tokens. `claude -p` in an empty directory, told only "what happened
  here?", read unlabelled and labelled sheets alike (every step, every value), so no
  skill or legend is needed. Tile labels carry `N/M` and `before switch` anyway: a reader
  inside this repo took the before-switch tiles for wasted near-duplicates
- gif, which frames (`Picker`, streamed: ffmpeg sends the distinct frames at a quarter size,
  gray, on stdout and their framemd5 times on a second pipe, each drained by a thread; the
  listing needs `-flush_packets 1` or it arrives only at the end). Pixels are quantised to
  16 levels and compared as Python ints (XOR, count zero bytes: C speed, stdlib). On UI and
  game footage switches are single frames of 20-99%: `SWITCH_AREA` 10%; the frame before
  each is always kept (evenly spread tiles missed 3 of 22 states in a 47 s game clip).
  The rest (A/B-tested 2026-09-27, blind `claude -p` readers, a synthetic 40 s clip with 16
  codes: moving and resting pointer, 0.3 s flash, 0.4 s toast, 1.5 s status line, typing,
  dialog, 8 s of motion): the old even spread, capped at 30, got 15/16 (missed the flash);
  the Picker 16/16 with 44 tiles, and 28 vs 30 / 23 vs 30 tiles on two real clips with
  equal or better stories. `STATE_AREA` 30x30 logical px since the last kept frame: 60x60
  and 40x40 lost the 1.5 s status line, 20x20 made every pointer rest a tile (91). Holding
  is judged at `BUSY_AREA` 60x60: at the same threshold a moving pointer made the screen
  "busy" and a 0.4 s toast was lost. Motion tiles only after 1 s of change, or a fade gets
  a mid-fade tile. Typing shows as its result, not word by word. No tile cap (the user's
  call: the filter decides); a 60 s all-motion full-screen clip is ~60 tiles, ~30 sheets
- gif, order: the indicator hides on the stop signal; the GIF (palette + GIF passes) is
  written and copied first, the sheets after (two more decodes: ~20 s + ~25 s for a 20 s
  full-screen game clip, vs ~35 s for everything before)
- Magnifier: drawn in `Canvas.do_snapshot` in device pixels (whole cells per physical px,
  NEAREST), so its grid is sharp at 1.3. Z is matched by hardware keycode as well as keyval:
  in the ru layout the key sends `я`. The toggle lives in the picker, not in a sway mode
  (a mode would eat Esc before the overlay sees it and needs a way out when capture exits)
- Window picking: wlroots' scene puts a logical rect on the output with `scale_box()`: both
  edges `round(v * scale)` in single precision, so neighbours share no pixel
  (`geometry.placed()`). Checked pixel-exact on headless sway at 1, 1.25, 4/3, 1.3, 1.5,
  1.75, 2 (tiled, split, floating, floating past the edge, tabbed with title bars,
  fullscreen). The last column/row inside is often the client's own partly covered pixel
  (GTK draws w * 1.3 = 393.9 px): it belongs to the window. Windows are not clipped in
  logical px: one past the output's edge also covers the strip past the last whole logical
  pixel. Tree workspaces carry no `visible`: the output's `current_workspace` names it;
  views carry `visible` (hidden tabs). A click replaced "click = start over". Hover
  keeps the shade (the user's pick of four mock-ups, 2026-09-28: lifting it over the
  hovered window made it go on, off, on as the pointer moved and a drag began)
- Dropped for good (2026-09-28): delay timer (the grab happens before the overlay maps
  and sway eats the binding, so menus and tooltips are already in the frozen frame),
  annotation incl. blur (Alt+Shift+P runs `drawdesk --image` after the shot), a bar
  "recording" module for whole-output gifs (it would be recorded too; 60 s cap and the
  done notification suffice), keeping popups on a window click (sway's tree has no
  popups; drag for those), `capture window`/`capture output` subcommands (focused, no
  picker: the picker's click covers them, and it previews what it takes), selection
  handles (the user: Esc and redo is enough; the magnifier makes the first drag exact)

### display — notes

- ddcutil scans every I2C bus on each call (~3.2 s here); `--bus N` takes ~0.07 s. The bus
  of the first display `ddcutil detect` lists (ddcutil's own default) is cached in
  `~/.cache/display/ddc-bus`; a call that fails on it rescans once and retries
- The popup's brightness writes run on a `LatestWriter` thread (newest value wins), never on
  the GTK main thread; a change still in its debounce and the writer's last value are
  flushed on close (Esc, backdrop, or widget-toggle's SIGTERM)

### audio — voice processing notes

- WebRTC in `webrtc-audio-processing-1` takes on/off switches only (no strengths);
  `webrtc.voice_detection` is left out: it marks speech and changes no sound
- Measured 2026-11-17 (the user's QuadCast S as placed for calls, speech through the speakers):
  the raw mic took the speakers at −56..−62 dB, the echo-cancelled one −101..−106 dB after
  it adapted (~4 s; again after the mic moves or the volume changes). A stream-restored
  volume (`pw-play` was at 40%) once made a test 24 dB quiet: play test audio with
  `paplay --volume=65536`
- Noise filters, measured 2026-11-17 on one typing + speech take (echo-cancelled input,
  5 ms frames, typing p99): input −56 dB, WebRTC −60, DeepFilterNet at its plugin
  defaults −66 (silent at our defaults, see `PLUGINS`), RNNoise −88;
  voice level the same in all. CPU per mono stream: RNNoise ~1% of a core, DeepFilterNet
  ~10%. The user preferred RNNoise by ear and dropped WebRTC's as useless. A neural
  filter gates: moments it takes for no speech come out silent, so soft speech or laughs
  can be cut (its threshold slider)
- While the unit restarts, WirePlumber falls back to the raw mic as the default source
  until the processed one is back (seen 2026-11-17): apps on Default get the raw mic for
  that moment

### audio — deferred features

- Passthrough formats (AC-3/DTS/… over HDMI/S/PDIF): skipped, no receiver here; `pactl set-sink-formats` covers it if one appears

### launcher — clipboard notes

- Forms per entry, tested by the user on 2026-11-11 (Telegram, Obsidian, ghostty, Claude Code):
  a GIF as file + path pastes animated in Telegram and Obsidian, the path in a terminal; GIF
  bytes paste as a still frame (so GIFs never go as bytes); a still image as bytes + file +
  path gives the picture in Telegram and the path in a terminal. The GNOME
  `x-special/gnome-copied-files` form added nothing
- `wl-copy -t text/uri-list` also offers the same bytes as `text/plain`, and Telegram takes
  that text for a GIF (a PNG it still attached): wl-copy can't offer a file without its text
  twin, hence `selection.py`
- Claude Code turns a pasted path to an image file into an `[Image #N]` attachment and
  sends the path with it (`[Image: source: …]`); a `file://` link stays text
- A pick is stored again (cliphist drops the older copy, new id; the cached file is renamed
  to the new id so the pasted path stays valid) and offers `MARKER`, which `cliphist-store`
  skips. A fresh image copy has no path of its own: its path is the cache file, alive
  while the entry is in the history (100). `--offer` never runs wl-copy (it would be
  stored again and loop)
- Chrome's "Copy image" offers `text/x-moz-url` (UTF-16 URL), `text/html`, `image/png` and
  no `text/plain`: a plain `wl-paste --watch` stored the URL. `cliphist-store` stores the
  image then, and `--offer` replaces Chrome's offer with bytes + file + path
- cliphist 0.7.0 drops a copy over 5,000,000 bytes (or blank) without a word: such a copy
  stays the app's own offer (no path) and is not in the history. `cliphist-store` offers
  only when the newest id changed across its store

### Backlog

- **network: mobile broadband (USB modems)** — postponed by the user on 2026-09-24, its
  own phase. First add `modemmanager` to arch-install; NetworkManager can't use modems
  without it (`mobile-broadband-provider-info` is already installed). Scope: a new-modem
  wizard (country → provider → APN from the provider database), SIM PIN/PUK unlock through
  `network-agent`, signal/operator/roaming state, an on/off switch in the popup, and a
  data-usage/metered hint. Hard; the user has USB modems to test with.

<!-- stack:start -->
## Stack

Chosen for this project with `stack add`. How to work with each is in
its rule and skills.
A dependency you add comes from the registry that `stack list` shows.
When a package there covers a need, run `stack add <name>`; the user
approves it first. When none does, ask the user before you write that
code yourself.

- **py-errors** (practices) — Errors: the project's exception classes; an expected failure is returned (Value | Error) and matched. Rule `.claude/rules/py-errors.md`.
- **pygobject** (ui) — Sway panels and popups with GTK 4 (PyGObject) and gtk4-layer-shell; tests run on a private headless Sway (tests/conftest.py). Rule `.claude/rules/pygobject.md`.
- **py-practices** (practices) — Before you write or change Python code, load the py-practices skill with the Skill tool. Skills `py-practices`.
<!-- stack:end -->
