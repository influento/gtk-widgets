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

Theme colors are defined in `themes/<name>.json`. At runtime, `render_css()` (`lib/theme.py`,
stdlib, re-exported by `lib/widget_base.py`) reads the theme file and replaces `@@TOKEN@@` placeholders in CSS with actual color values. The
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
- Close via Escape/q key or clicking outside the widget
- Shared components live in `lib/` beside the base class: `CopyLabel` (`lib/copy_label.py`)
  is a label that copies its text (or a longer copy text) to the clipboard on click;
  `copyable(label, on)` gives a plain label the same click-to-copy. Every error line
  shown in a widget is copyable (status labels switch it on only while showing an error).
  `popup_window()`/`show_popup()`/`install_css()` in `lib/widget_base.py` build the same
  layer-shell overlay for long-running apps that open popups on demand (`network-agent`);
  `place_popup()` places the container without presenting, for an app that builds its
  window once and shows/hides it (`launcher`)
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
| `usb`          | USB device manager: list, mount/unmount (click path to copy), fix partition type for Mac/Windows, format, write ISO with progress (root helper via polkit) |
| `timer`        | Timer + stopwatch with session-scoped state, alarm on expiry      |
| `audio`        | pavucontrol replacement via vendored pulsectl: playback/recording streams, output/input devices, card profiles, peak meters, input test recording |
| `launcher`     | wofi replacement, resident (`launcher --daemon`, toggled by `launcher`): drun (desktop entries, should_show, tiers exact > prefix > word start > substring > fuzzy on the name, then generic name/keywords/executable, ties by launch counts halving every 2 weeks in `~/.cache/launcher/usage.json`, ЙЦУКЕН keys mapped to us Latin, Terminal=true via `ghostty -e`) and `--dmenu [--prompt] [--after-tab]` (stdin lines, prints the pick byte-exact, Esc = exit 1). The CLI is stdlib-only and talks to the instance over `$XDG_RUNTIME_DIR/gtk-widgets-launcher.sock` (importing gi alone costs ~60 ms); with no instance a toggle starts one, a dmenu runs one-shot. Only Esc closes it |
| `network`      | nm-applet replacement over libnm: networking/Wi-Fi switches, wired, Wi-Fi list (connect, inline password, hidden, hotspot), mutually exclusive VPN and Proxy sections (a chip per VPN profile, Proxy rules: per-app SOCKS5 routing through sing-box, with a Proxy rules page; clicking the active chip turns it off; each title line shows its state, including when the other one is on), details, captive-portal/limited notice, Enterprise (PEAP/TTLS) join form, Connections page (delete, WireGuard import/export), Edit page for Wi-Fi/Ethernet/WireGuard profiles; `network-agent` = notifications + secret agent prompt; `network-status` = long-running bar status (link, VPN, connectivity) |
| `capture`      | Region screenshots at the output's own pixels: `capture region [--dir DIR] [--copy]` grabs every output's raw framebuffer (stdlib wlr-screencopy client, before gi is imported), shows the frozen frames in one overlay per output, saves the drag cut from the raw buffer in physical pixels (no resampling at fractional scales), prints the path; Z (by keycode, so also in the ru layout) toggles a magnifier while picking (loupe of 13x13 physical px, pixel position and colour; off at start); `--copy` = `text/uri-list` via wl-copy. Exit 0 saved, 1 cancelled (Esc, right click) or already open (flock), 2 error. Scale from sway IPC snapped to 1/120 (Gdk.Monitor.get_scale() is a ratio of rounded sizes). `capture gif [--dir DIR] [--copy]`: same picker, then wf-recorder (lossless RGB, 30 fps, 60 s cap) with a click-through indicator outside the region; a second `capture gif` stops it (pid file + SIGUSR1), `--cancel` discards it (SIGUSR2); the indicator goes at once; ffmpeg makes `DIR/recording-STAMP/` = `recording.gif` first (every frame, exact duplicates merged; `--copy` copies it right away), then `sheet.png` (frames showing a new state, no cap, tiled under `N/M · time · before switch` labels, for AI; `sheet-N.png` when they need several) and `frames/`; `--copy` then copies the sheets in one list (on top); a notification when done or failed |

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
│   ├── widget_base.py     # Shared GTK4 popup base class
│   ├── theme.py           # Theme file lookup, colours, @@TOKEN@@ rendering (stdlib, no GTK)
│   ├── copy_label.py      # CopyLabel + copyable(): click copies text via wl-copy, flashes "Copied"
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
│   ├── launcher/
│   │   ├── main.py        # CLI: stdlib fast path to the instance; else detach, preload layer-shell, start it
│   │   ├── app.py         # Picker popup (ListView, built once), resident Launcher + socket server, one-shot dmenu
│   │   ├── apps.py        # Desktop entries, usage decay (atomic JSON), launch (terminal wrap, no LD_PRELOAD leak)
│   │   ├── match.py       # Match tiers, secondary fields, ru->us key mapping (no GTK)
│   │   ├── protocol.py    # CLI <-> instance wire format (stdlib)
│   │   └── style.css
│   ├── capture/
│   │   ├── main.py        # CLI: lock, grab (stdlib), ctypes-load layer-shell (no re-exec), pick, save, copy; gif flow, stop/cancel signals, clipboard order
│   │   ├── screencopy.py  # Wayland wire client: wlr-screencopy of every output into one memfd (stdlib)
│   │   ├── swayipc.py     # Exact output scales and logical rects from sway IPC (stdlib)
│   │   ├── geometry.py    # Logical -> physical selection maths (no GTK)
│   │   ├── image.py       # Upright frames (lossless flips/turns), row-slice crops, PNG save
│   │   ├── record.py      # gif: logical region + crop that record the exact physical pixels, wf-recorder start/stop (no GTK)
│   │   ├── process.py     # gif: ffmpeg GIF, sheet frames, contact sheets; `python3 process.py DIR SCALE` reruns a failed one (no GTK)
│   │   ├── app.py         # Overlay per output: frozen frame drawn 1:1, shade, selection frame; gif's recording indicator
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
- Planned: window/output picking, drawing and annotation, selection handles,
  delay timer (new subcommands beside `region` and `gif`)

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
