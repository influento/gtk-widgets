# gtk-widgets

GTK4 popup widgets for Sway (Wayland), themed with Catppuccin Mocha.

## Widgets

| Widget         | Description                                                |
| -------------- | ---------------------------------------------------------- |
| `calendar`     | GTK4 calendar                                              |
| `display`      | Display settings: scale, brightness, night light; `display-brightness` CLI for keybinds |
| `claude-usage` | Claude subscription usage with progress bars               |
| `bluetooth`    | Bluetooth device manager: scan, pair, connect/disconnect   |
| `power`        | Power menu: lock, sleep, reboot, shut down                 |
| `translate`    | ezpick text tool: translate, fix English, dictionary (via `claude` CLI) |
| `usb`          | USB device manager: list, mount/unmount, Mac/Windows type fix, format, write ISO (root helper via polkit) |
| `timer`        | Timer + stopwatch with alarm on expiry                     |
| `audio`        | pavucontrol replacement: streams, devices, ports, profiles, peak meters (live via pulse events) |
| `launcher`     | App launcher (drun) and dmenu picker, a wofi replacement: resident instance, ranked fuzzy search with usage history, ЙЦУКЕН keys map to Latin |
| `network`      | nm-applet replacement via libnm: Wi-Fi/wired, mutually exclusive VPN and Proxy sections (WireGuard/VPN profile chips, or Proxy rules: per-app SOCKS5 routing through sing-box; clicking the active chip turns it off), hidden and Enterprise (PEAP/TTLS) networks, hotspot, connection list, WireGuard import/export, per-profile Edit page (Wi-Fi/Ethernet/WireGuard); `network-agent` for notifications + password prompts |
| `capture`      | Screenshots and short screen recordings at the output's own pixels: freezes every output, drag a region, saved without any resampling at fractional scales; `gif` records it as a GIF plus a contact sheet for AI |

## Installation

Requires Python 3, GTK4, and [gtk4-layer-shell](https://github.com/wmww/gtk4-layer-shell).
`audio` also needs `libpulse` and a PulseAudio-compatible server such as `pipewire-pulse`;
its Python bindings ([pulsectl](https://github.com/mk-fg/python-pulse-control)) are vendored
in `lib/pulsectl/`.
`network` needs NetworkManager's `libnm` (GObject introspection data, `NM-1.0.typelib`) and
`notify-send` for `network-agent`'s notifications. It doesn't use `nm-connection-editor`:
settings the Edit page doesn't cover aren't editable from the widget. The Edit page shows
WireGuard public keys with `wg` (wireguard-tools) when it is installed. Proxy rules needs
`sing-box` (Arch `extra`, 1.14 or later) and `nftables` for its optional kill switch.

```bash
./install.sh                          # default theme (catppuccin-mocha)
./install.sh --theme <name>           # any themes/<name>.json (only catppuccin-mocha is bundled)
```

`--theme` points `themes/current.json` at the chosen file; `GTK_WIDGETS_THEME=<file>`
overrides it for a single process.

This symlinks into `~/.local/bin/`:

- `widget-toggle` — shared toggle script (launch/dismiss via flock)
- `<name>` — each popup (e.g., `calendar`, `bluetooth`)
- `<name>-status` — each status script, if present (e.g., `calendar-status`)
- `<widget>-<tool>` — extra CLI entry points (e.g., `display-brightness up|down|set|get`)

The root helpers (`usb-helper`, `proxy-helper`) and their polkit rules are copied to
`/usr/lib/gtk-widgets/` and `/etc/polkit-1/rules.d/` with `sudo` (only when they changed),
and the Proxy rules unit to `/etc/systemd/system/gtk-widgets-proxy.service` (never enabled:
it starts when Proxy rules is picked in the popup).

## Waybar Integration

Each widget with a `status` script can be used as a waybar custom module.
The popup is toggled via `widget-toggle <name>` on click.

| Widget         | Status command        | Interval | On-click                     |
| -------------- | --------------------- | -------- | ---------------------------- |
| `calendar`     | `calendar-status`     | 60       | `widget-toggle calendar`     |
| `bluetooth`    | `bluetooth-status`    | 5        | `widget-toggle bluetooth`    |
| `claude-usage` | `claude-usage-status` | 600      | `widget-toggle claude-usage` |
| `display`      | `display-status`      | once     | `widget-toggle display`      |
| `power`        | `power-status`        | once     | `widget-toggle power`        |
| `usb`          | `usb-status`          | 3        | `widget-toggle usb`          |
| `timer`        | `timer-status`        | 1        | `widget-toggle timer`        |
| `network`      | `network-status`      | none     | `widget-toggle network`      |

Status scripts output JSON with `text` (required), `tooltip` and `class` (optional).

Waybar module example:

```json
"custom/calendar": {
  "exec": "calendar-status",
  "interval": 60,
  "tooltip": false,
  "on-click": "bash -c \"$HOME/.local/bin/widget-toggle calendar\""
}
```

`translate` has no status script — it is triggered by a keybinding, not a waybar module.
`audio` has none either; waybar's built-in `pulseaudio` module shows the volume and opens it
with `widget-toggle audio`.
`network-status` is long-running: it follows NetworkManager and prints a line on every
change, so give it no `interval`. It shows the connection carrying traffic, the active VPN
and NM's connectivity check; `class` is a list (`wifi`/`wired`/`hotspot`/`other`/
`disconnected`/`disabled`/`error`, plus `portal`/`limited`/`none`, plus `vpn`, plus `proxy`
while Proxy rules is on or `proxy-down` when sing-box failed) for styling.
`network-status --once` prints the current state and exits.

```json
"custom/network": {
  "exec": "network-status",
  "return-type": "json",
  "restart-interval": 5,
  "on-click": "bash -c \"$HOME/.local/bin/widget-toggle network\""
}
```

`network-agent` is a long-running companion (connect/disconnect/VPN/captive-portal notifications,
Proxy rules on/off/crashed and proxies that stop answering, and a
NetworkManager secret agent that prompts for passwords); start it once from the compositor
(e.g. `exec network-agent` in sway) instead of nm-applet.

## Launcher

`launcher` stays resident (one GTK application, `dev.dotfiles.launcher`) so it shows in a
frame or two instead of paying the Python + GTK start-up on every key press. Start it hidden
from the compositor and bind the toggle; `launcher --dmenu` reads lines on stdin and prints
the chosen one exactly as read (Esc prints nothing and exits 1):

```
exec launcher --daemon
bindsym $mod+d exec launcher
bindsym $mod+v exec sh -c 'sel=$(cliphist list | launcher --dmenu --prompt Clipboard --after-tab) && printf "%s\n" "$sel" | cliphist decode | wl-copy'
```

(A plain `… | launcher --dmenu | cliphist decode | wl-copy` pipe would still run `wl-copy`
after Esc, on empty input.) `--after-tab` shows and searches only what follows a line's first
tab, so cliphist's ids stay hidden but still reach `cliphist decode`.

Without a running instance, `launcher` starts one and shows it, and `--dmenu` runs as a
one-shot process (slower, ~200 ms). The CLI talks to the instance over
`$XDG_RUNTIME_DIR/gtk-widgets-launcher.sock`. Search matches names, then generic names,
keywords and executables (exact > prefix > word start > substring > fuzzy), breaks ties
by launch counts that halve every two weeks (`~/.cache/launcher/usage.json`), and maps keys
typed on the ru layout to the us letters in the same place. `Terminal=true` entries run
in `ghostty -e`. Only Esc closes it (q is typeable); ↑/↓, Tab/Shift+Tab, Ctrl+j/k,
Ctrl+n/p and PgUp/PgDn move the selection. Set `LAUNCHER_T0=$(date +%s%N)` on a call to
have the instance print the time to its first frame on stderr.

## Capture

`capture region` grabs every output's framebuffer with wlr-screencopy (a small stdlib
Wayland client, before GTK is loaded), then shows those frozen frames in an overlay per
output. Drag a rectangle; releasing saves it to `DIR/screenshot-%Y%m%d-%H%M%S.png` and prints
the absolute path. Esc or a right click cancels (exit 1, no file, clipboard untouched); a
second `capture` while one is open exits 1 at once. Z (the key, in any layout) turns a
magnifier on and off while picking: a loupe beside the pointer shows the 13x13 physical
pixels around it, unsmoothed, with the one a corner would land on outlined (and the
selection's edges while dragging) and its position and colour below. It starts off each
time and is never in the saved image.

```
bindsym $mod+p exec capture region --dir ~/pictures/screenshots --copy
bindsym $mod+Shift+p exec sh -c 'f=$(capture region --dir ~/pictures/screenshots) && drawdesk --image "$f"'
```

`--copy` puts `file://<path>` on the clipboard as `text/uri-list` (needs `wl-copy`). `--dir`
defaults to `$XDG_PICTURES_DIR/screenshots`. The PNG is cut from the raw buffer in physical
pixels and never resampled, so it stays sharp at any fractional scale (a full 3840x1600 output
at 1.3 saves as 3840x1600). The scale comes from sway's IPC (`GetOutputs`);
without sway, from the surface's fractional scale. A drag stays on the output it started on.
The last physical column/row that a fractional scale leaves outside the logical layout (black)
is out of reach. Set `CAPTURE_T0=$(date +%s%N)` to print the grab and first-paint times.

`capture gif` picks a region the same way and records it with `wf-recorder` (30 fps,
lossless RGB) until `capture gif` runs again, or for 60 s at most. While it records, a red
frame and an elapsed-time label sit just outside the region; they take no clicks and no
keyboard, and are not in the recording; they go the moment it stops. `capture gif --cancel`
stops a recording and throws it away (exit 1 when none is going). Then `ffmpeg` writes
`DIR/recording-%Y%m%d-%H%M%S/`, the GIF first:

- `recording.gif` — every frame, physical size, palette made for the clip, loops forever;
  only exact duplicates are merged (into the previous frame's delay)
- `sheet.png` — the frames that show something new, tiled for an AI to read (chat AIs read
  only the first frame of a GIF). A frame is kept when 30x30 logical px or more changed
  since the last kept one and the screen then holds for 0.2 s (a moving pointer doesn't
  stop it holding; its rests are kept). While the screen keeps changing for over 1 s
  (scrolling, video, a game), one frame a second. Each screen switch (a dialog, menu or
  page: 10% or more of the region changing at once) keeps the frame just before it, which
  shows what was clicked. There is no cap: the tiles follow the content. Each tile's label
  gives its place, its time and whether the screen switches right after it
  (`3/30 · 02.100s · before switch`), so the sheets need no legend. A sheet is at most
  2000x2000 px, the most Claude shows of an image, and shrinks a frame at most to 0.65 px
  per logical px, so 10 px UI text stays readable (tested on random codes: exact at
  6.5 px, half at 4.4 px). Frames that don't fit one sheet that way go on `sheet-1.png`,
  `sheet-2.png`, ... (a full 4K screen at 1.3: two a sheet); tiles run left to right, top
  to bottom, on from one sheet to the next. The sheets cost an AI about the same tokens as
  those frames one by one (text must stay as big): they save images to paste, not tokens;
  the frame choice is what saves
- `frames/` — those frames at full size, named `NNNN-SS.sssS.png`

It prints the folder's path and sends a notification when the sheets are done (or when
processing fails). `--copy` puts `file://<path>` of the GIF on the clipboard
(`text/uri-list`, as for screenshots) as soon as it is written, then of the sheets (one
list), so a plain paste gives the sheets and the GIF is next in the clipboard history (it
waits up to 2 s for `cliphist` to have stored the GIF). `--dir` defaults to
`$XDG_PICTURES_DIR/recordings`. If processing fails, the folder keeps `raw.mkv`;
`python3 widgets/capture/process.py <folder> <scale>` runs it again (the command is printed). Needs `wf-recorder`, `ffmpeg`, `notify-send` and, for
`--copy`, `wl-clipboard` and `cliphist`. Rotated or flipped outputs aren't supported.

```
bindsym $mod+Shift+g exec capture gif --dir ~/pictures/recordings --copy
bindsym $mod+Ctrl+g exec capture gif --cancel
```

> **Privacy:** `translate` sends the current text selection to Anthropic (via the `claude` CLI)
> each time it runs. Avoid triggering it on sensitive text.
