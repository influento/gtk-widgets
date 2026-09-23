# gtk-widgets

## Project Overview

GTK4 widget toolkit for Sway (Wayland). A collection of self-contained popup widgets
themed via Catppuccin Mocha tokens, toggled via `widget-toggle`.

This repository is responsible only for widget UI and the data each widget exposes.
Desktop integration (waybar modules, keybindings, sway config) lives in dotfiles —
this repo provides the building blocks, dotfiles wires them up.

## Architecture

Each widget lives in its own directory under `widgets/<name>/` with:

- `main.py` — popup UI, subclasses `WidgetPopup` from `lib/widget_base.py`
- `style.css` — CSS with `@@TOKEN@@` placeholders, rendered at runtime by `load_css()`
- `status` (optional) — outputs JSON for status bars or CLI use

All widgets share a common base class (`lib/widget_base.py`) that handles layer-shell
setup, transparent backdrop, Esc/q dismiss, and CSS loading with theme token replacement.

### Theming

Theme colors are defined in `themes/<name>.json`. At runtime, `render_css()` reads the
theme file and replaces `@@TOKEN@@` placeholders in CSS with actual color values. The
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
- `widget-toggle <name>` handles launch/dismiss via `flock` (prevents duplicates)
- Close via Escape/q key or clicking outside the widget
- Widgets with a `status` script (bash or Python) output JSON (`text`, `tooltip`, `class`) for status bars
- Extra executable `<widget>/<name>.py` files are symlinked as `<widget>-<name>` CLI entry points (e.g. `display-brightness`, bound to XF86MonBrightness keys in dotfiles)

### Current widgets

| Widget         | Description                                                       |
| -------------- | ----------------------------------------------------------------- |
| `calendar`     | GTK4 calendar                                                     |
| `display`      | Display settings: scale, brightness, night light temp; `display-brightness` CLI for keybinds |
| `claude-usage` | Claude usage: 5h session, weekly all-models, weekly per-model     |
| `bluetooth`    | Bluetooth device manager: scan, pair, connect/disconnect          |
| `power`        | Power menu: lock, sleep, reboot, shut down                        |
| `translate`    | ezpick text tool (`dev.dotfiles.ezpick`): translate, fix English, dictionary via `claude` CLI |
| `usb`          | USB device manager: list, format, write ISO with progress (root helper via polkit) |
| `timer`        | Timer + stopwatch with session-scoped state, alarm on expiry      |
| `audio`        | pavucontrol replacement via vendored pulsectl: playback/recording streams, output/input devices, card profiles, peak meters |

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
  if a binding is unavoidable, vendor a pinned, audited copy under `lib/` (as `lib/pulsectl/`,
  ctypes over libpulse, used by `audio`) with its license and a note of local changes
- Before every commit/push, audit the staged diff for sensitive information leaks

## File Structure

```
gtk-widgets/
├── CLAUDE.md
├── README.md
├── install.sh             # Symlinks widgets + scripts into ~/.local/bin; installs usb-helper + polkit rule (sudo)
├── widget-toggle          # Generic toggle for GTK4 popups (flock-based)
├── lib/
│   ├── widget_base.py     # Shared GTK4 popup base class + theme loader
│   └── pulsectl/          # Vendored libpulse ctypes bindings (upstream commit + changes in README.md)
├── polkit/
│   ├── usb-helper         # Root helper for USB format/write, installed to /usr/lib/gtk-widgets/
│   └── 50-gtk-widgets-usb.rules  # Polkit rule that authorises only that helper
├── widgets/
│   ├── bluetooth/
│   │   ├── main.py
│   │   ├── style.css
│   │   └── status         # JSON: icon, connection count
│   ├── calendar/
│   │   ├── main.py
│   │   ├── style.css
│   │   └── status         # JSON: date/time with icon
│   ├── claude-usage/
│   │   ├── main.py
│   │   ├── usage.py       # Shared formatting (reset/charge dates, severity) for popup + status
│   │   ├── style.css
│   │   └── status         # JSON: usage percentages, reset times
│   ├── display/
│   │   ├── main.py
│   │   ├── brightness.py  # Backend (backlight/DDC) + CLI: display-brightness up|down|set|get
│   │   ├── style.css
│   │   └── status         # JSON: display icon
│   ├── power/
│   │   ├── main.py
│   │   ├── style.css
│   │   └── status         # JSON: power icon
│   ├── translate/
│   │   ├── main.py
│   │   └── style.css
│   ├── usb/
│   │   ├── main.py
│   │   ├── style.css
│   │   └── status         # JSON: USB icon, event-driven via udevadm
│   ├── timer/
│   │   ├── main.py
│   │   ├── state.py       # Shared state model (popup + status script), alarm fires once
│   │   ├── style.css
│   │   └── status         # JSON: hh:mm:ss, fires alarm at zero
│   └── audio/
│       ├── main.py        # pulsectl: event thread + main-thread command connection, rows updated in place
│       ├── meters.py      # Peak meter streams on their own connection + thread (visible tab only)
│       └── style.css
└── themes/
    ├── catppuccin-mocha.json
    └── current.json       # Symlink to the active theme (created by install.sh)
```

## Planned Evolution

### ezpick — Multi-Action Text Tool

`widgets/translate` (application id `dev.dotfiles.ezpick`) is the multi-action text tool
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

### audio — deferred features

- Passthrough formats (AC-3/DTS/… over HDMI/S/PDIF): skipped, no receiver here; `pactl set-sink-formats` covers it if one appears
- Dotfiles: point waybar's `pulseaudio` `on-click-right` at `widget-toggle audio` once parity
  is confirmed (keep `pavucontrol-toggle` until then)

### Backlog

- **display: DDC writes off the main thread** — `set_pct` still runs `ddcutil setvcp`
  on the GTK main thread, so dragging the slider on an external DDC monitor stalls the
  popup a few hundred ms per step (the sysfs backlight path is instant). Fix: worker
  thread with a latest-value-wins queue so drags coalesce; verify with the fake DDC
  backend that the main loop no longer stalls and the final value matches the last drag.
