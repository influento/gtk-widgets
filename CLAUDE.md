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

Theme colors are defined in `themes/catppuccin-mocha.json`. At runtime, `load_css()`
reads the theme file and replaces `@@TOKEN@@` placeholders in CSS with actual color
values. Override the theme file path via `GTK_WIDGETS_THEME` env var.

### How widgets work

- Each widget is a self-contained GTK4 + Python app using `gtk4-layer-shell`
- Layer-shell creates a fullscreen transparent overlay that catches clicks (backdrop dismiss)
- Widgets are themed via CSS with Catppuccin Mocha colors
- `widget-toggle <name>` handles launch/dismiss via `flock` (prevents duplicates)
- Close via Escape/q key or clicking outside the widget
- Widgets with a `status` script output JSON (`text`, `tooltip`, `class`) for status bars

### Current widgets

| Widget         | Description                                                       |
| -------------- | ----------------------------------------------------------------- |
| `calendar`     | GTK4 calendar                                                     |
| `display`      | Display settings: scale, brightness (laptop), night light temp    |
| `claude-usage` | Claude subscription usage with progress bars                      |
| `bluetooth`    | Bluetooth device manager: scan, pair, connect/disconnect          |
| `power`        | Power menu: lock, sleep, reboot, shut down                        |
| `translate`    | Translation via Claude Sonnet (prototype of ezpick action system) |
| `usb`          | USB device manager: list, format, write ISO with progress         |

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
3. Set `GTK_WIDGETS_THEME` env var to point to the new file

## Widget Design Rules

- Every widget container MUST have `border: 1px solid @@SURFACE1@@` and `border-radius: 8px`
  — the border must be on the outermost container so it's flush with the widget edge
- Disable built-in borders and backgrounds on GTK widgets inside the container
- Window background is always `transparent` (layer-shell overlay)
- Font: `"JetBrainsMono Nerd Font", monospace`
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
- Python widgets use standard library only (+ PyGObject)
- Never add `Co-Authored-By` trailers to git commits
- Before every commit/push, audit the staged diff for sensitive information leaks

## File Structure

```
gtk-widgets/
├── CLAUDE.md
├── install.sh             # Symlinks widgets + scripts into ~/.local/bin
├── widget-toggle          # Generic toggle for GTK4 popups (flock-based)
├── lib/
│   └── widget_base.py     # Shared GTK4 popup base class + theme loader
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
│   │   ├── style.css
│   │   └── status         # JSON: usage percentages, reset times
│   ├── display/
│   │   ├── main.py
│   │   ├── style.css
│   │   └── status         # JSON: display icon
│   ├── power/
│   │   ├── main.py
│   │   ├── style.css
│   │   └── status         # JSON: power icon
│   ├── translate/
│   │   ├── main.py
│   │   └── style.css
│   └── usb/
│       ├── main.py
│       ├── style.css
│       └── status         # JSON: USB icon, event-driven via udevadm
└── themes/
    └── catppuccin-mocha.json
```

## Planned Evolution

### ezpick — Multi-Action Text Tool

The `translate-popup` will evolve into a multi-action tool triggered by Super+T:

**Actions:**

- **Translate** — auto-detect direction (EN↔RU default), language dropdown override
- **Fix English** — correct grammar/style with inline explanations
- **Explain** — explain selected text/concept
- **Summarize** — condense text or URL content

**Input modes (single shortcut):**

- **Text selected** → opens with text pre-filled, defaults to Translate
- **Nothing selected** → opens empty with text input for typing/pasting
- URL detection: if input starts with `http`, auto-fetch page content before passing to Claude
