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
- Shared components live in `lib/` beside the base class: `CopyLabel` (`lib/copy_label.py`)
  is a label that copies its text (or a longer copy text) to the clipboard on click.
  `popup_window()`/`show_popup()`/`install_css()` in `lib/widget_base.py` build the same
  layer-shell overlay for long-running apps that open popups on demand (`network-agent`)
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
| `audio`        | pavucontrol replacement via vendored pulsectl: playback/recording streams, output/input devices, card profiles, peak meters, input test recording |
| `network`      | nm-applet replacement over libnm: networking/Wi-Fi switches, wired, Wi-Fi list (connect, inline password, hidden, hotspot), mutually exclusive VPN and Proxy sections (a chip per VPN profile, Proxy rules: per-app SOCKS5 routing through sing-box, with a Proxy rules page; clicking the active chip turns it off; each title line shows its state, including when the other one is on), details, captive-portal/limited notice, Enterprise (PEAP/TTLS) join form, Connections page (delete, WireGuard import/export), Edit page for Wi-Fi/Ethernet/WireGuard profiles; `network-agent` = notifications + secret agent prompt; `network-status` = long-running bar status (link, VPN, connectivity) |

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
  if a binding is unavoidable, vendor a pinned, audited copy under `lib/` (as `lib/pulsectl/`,
  ctypes over libpulse, used by `audio`) with its license and a note of local changes
- Before every commit/push, audit the staged diff for sensitive information leaks

## File Structure

```
gtk-widgets/
├── CLAUDE.md
├── README.md
├── install.sh             # Symlinks widgets + scripts into ~/.local/bin; installs root helpers, polkit rules, proxy unit (sudo)
├── widget-toggle          # Generic toggle for GTK4 popups (flock-based)
├── lib/
│   ├── widget_base.py     # Shared GTK4 popup base class + theme loader
│   ├── copy_label.py      # CopyLabel: click copies text via wl-copy, flashes "Copied"
│   └── pulsectl/          # Vendored libpulse ctypes bindings (upstream commit + changes in README.md)
├── polkit/
│   ├── usb-helper         # Root helper for USB format/write, installed to /usr/lib/gtk-widgets/
│   ├── 50-gtk-widgets-usb.rules  # Polkit rule that authorises only that helper
│   ├── proxy-helper       # Root helper: validates a Proxy rules request, builds the sing-box config, starts/stops the unit
│   ├── 50-gtk-widgets-proxy.rules  # Polkit rule that authorises only that helper
│   └── gtk-widgets-proxy.service   # sing-box unit (User=sing-box), installed to /etc/systemd/system/, never enabled
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
│   ├── audio/
│   │   ├── main.py        # pulsectl: event thread + main-thread command connection, rows updated in place
│   │   ├── meters.py      # Peak meter streams on their own connection + thread (visible tab only)
│   │   ├── recorder.py    # Input test recording: parec into memory (30 s cap), pacat playback, discard
│   │   └── style.css
│   └── network/
│       ├── main.py        # libnm popup: async calls, debounced sync of keyed rows; Connections page
│       ├── editor.py      # Edit page: per-profile settings on a clone, verify(), full-secret saves, reapply on save (Reconnect now when refused)
│       ├── ui.py          # Small GTK helpers shared by main.py and editor.py
│       ├── agent.py       # network-agent: connection notifications + NM.SecretAgentOld password prompt
│       ├── nmutil.py      # Shared libnm helpers: profile builders, reasons, connectivity, WireGuard .conf export
│       ├── proxy.py       # Proxy rules model: state file (0600), paste parser, helper call, unit watch (D-Bus)
│       ├── proxypage.py   # Proxy rules page: proxies (paste, check, Block QUIC), app rules, default exit, kill switch
│       ├── socks5.py      # Minimal SOCKS5 client: login, CONNECT trace (exit IP, country, latency), UDP ASSOCIATE round trip
│       ├── style.css      # Also styles network-agent's prompt
│       └── status         # JSON: link, active VPN, Proxy rules, connectivity; long-running (one line per change)
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

### audio — deferred features

- Passthrough formats (AC-3/DTS/… over HDMI/S/PDIF): skipped, no receiver here; `pactl set-sink-formats` covers it if one appears

### Backlog

- **display: DDC writes off the main thread** — `set_pct` still runs `ddcutil setvcp`
  on the GTK main thread, so dragging the slider on an external DDC monitor stalls the
  popup a few hundred ms per step (the sysfs backlight path is instant). Fix: worker
  thread with a latest-value-wins queue so drags coalesce; verify with the fake DDC
  backend that the main loop no longer stalls and the final value matches the last drag.
- **network: mobile broadband (USB modems)** — postponed by the user on 2026-09-24, its
  own phase. First add `modemmanager` to arch-install; NetworkManager can't use modems
  without it (`mobile-broadband-provider-info` is already installed). Scope: a new-modem
  wizard (country → provider → APN from the provider database), SIM PIN/PUK unlock through
  `network-agent`, signal/operator/roaming state, an on/off switch in the popup, and a
  data-usage/metered hint. Hard; the user has USB modems to test with.
