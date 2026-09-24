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
| `network`      | nm-applet replacement via libnm: Wi-Fi/wired, mutually exclusive VPN and Proxy sections (WireGuard/VPN profile chips, or Proxy rules: per-app SOCKS5 routing through sing-box; clicking the active chip turns it off), hidden and Enterprise (PEAP/TTLS) networks, hotspot, connection list, WireGuard import/export, per-profile Edit page (Wi-Fi/Ethernet/WireGuard); `network-agent` for notifications + password prompts |

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

> **Privacy:** `translate` sends the current text selection to Anthropic (via the `claude` CLI)
> each time it runs. Avoid triggering it on sensitive text.
