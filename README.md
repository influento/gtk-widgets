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
| `usb`          | USB device manager: list, format, write ISO (root helper via polkit) |
| `timer`        | Timer + stopwatch with alarm on expiry                     |

## Installation

Requires Python 3, GTK4, and [gtk4-layer-shell](https://github.com/wmww/gtk4-layer-shell).

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

The USB helper and its polkit rule are copied to `/usr/lib/gtk-widgets/usb-helper` and
`/etc/polkit-1/rules.d/` with `sudo` (only when they changed).

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

> **Privacy:** `translate` sends the current text selection to Anthropic (via the `claude` CLI)
> each time it runs. Avoid triggering it on sensitive text.
