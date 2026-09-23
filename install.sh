#!/usr/bin/env bash
set -euo pipefail

# Install gtk-widgets: symlink popups, status scripts, and widget-toggle into ~/.local/bin;
# install the root helpers, their polkit rules and the Proxy rules unit (sudo)
# Usage: install.sh [--theme <name>]   (default: catppuccin-mocha)

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
THEME="catppuccin-mocha"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --theme) THEME="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Theme symlink
theme_file="$REPO_DIR/themes/${THEME}.json"
if [[ ! -f "$theme_file" ]]; then
  echo "Theme not found: $theme_file" >&2
  exit 1
fi
ln -sfn "$theme_file" "$REPO_DIR/themes/current.json"
echo "  theme: $THEME"

mkdir -p "$BIN_DIR"

# widget-toggle
ln -sfn "$REPO_DIR/widget-toggle" "$BIN_DIR/widget-toggle"
echo "  widget-toggle"

# Widgets
for widget_dir in "$REPO_DIR"/widgets/*/; do
  name="$(basename "$widget_dir")"
  main="$widget_dir/main.py"

  if [[ -f "$main" ]]; then
    ln -sfn "$main" "$BIN_DIR/$name"
    echo "  $name"
  fi

  status="$widget_dir/status"
  if [[ -f "$status" ]]; then
    ln -sfn "$status" "$BIN_DIR/${name}-status"
    echo "  ${name}-status"
  fi

  # Extra CLI entry points (e.g. display/brightness.py -> display-brightness)
  for extra in "$widget_dir"/*.py; do
    [[ -x "$extra" && "$(basename "$extra")" != "main.py" ]] || continue
    cli="${name}-$(basename "$extra" .py)"
    ln -sfn "$extra" "$BIN_DIR/$cli"
    echo "  $cli"
  done
done

# Privileged helpers + polkit rules (requires sudo). Each rule authorises only
# its helper, so install the helpers root-owned at a fixed path.
for helper in usb-helper proxy-helper; do
  helper_src="$REPO_DIR/polkit/$helper"
  helper_dst="/usr/lib/gtk-widgets/$helper"
  if [[ -f "$helper_src" ]]; then
    if [[ ! -f "$helper_dst" ]] || ! diff -q "$helper_src" "$helper_dst" &>/dev/null; then
      sudo install -D -m 0755 -o root -g root "$helper_src" "$helper_dst"
      echo "  helper: $helper_dst"
    fi
  fi
done

for polkit_src in "$REPO_DIR"/polkit/*.rules; do
  polkit_dst="/etc/polkit-1/rules.d/$(basename "$polkit_src")"
  if [[ ! -f "$polkit_dst" ]] || ! diff -q "$polkit_src" "$polkit_dst" &>/dev/null; then
    sudo install -m 0644 -o root -g root "$polkit_src" "$polkit_dst"
    echo "  polkit: $(basename "$polkit_src")"
  fi
done

# sing-box unit for the network widget's Proxy rules (never enabled at boot)
unit_src="$REPO_DIR/polkit/gtk-widgets-proxy.service"
unit_dst="/etc/systemd/system/gtk-widgets-proxy.service"
if [[ ! -f "$unit_dst" ]] || ! diff -q "$unit_src" "$unit_dst" &>/dev/null; then
  sudo install -m 0644 -o root -g root "$unit_src" "$unit_dst"
  sudo systemctl daemon-reload
  echo "  unit: gtk-widgets-proxy.service"
fi
if ! command -v sing-box &>/dev/null; then
  echo "  note: Proxy rules needs sing-box (pacman -S sing-box)"
fi

echo "done"
