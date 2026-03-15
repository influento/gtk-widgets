#!/usr/bin/env bash
set -euo pipefail

# Install gtk-widgets: symlink popups, status scripts, and widget-toggle into ~/.local/bin
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
ln -sf "$theme_file" "$REPO_DIR/themes/current.json"
echo "  theme: $THEME"

mkdir -p "$BIN_DIR"

# widget-toggle
ln -sf "$REPO_DIR/widget-toggle" "$BIN_DIR/widget-toggle"
echo "  widget-toggle"

# Widgets
for widget_dir in "$REPO_DIR"/widgets/*/; do
  name="$(basename "$widget_dir")"
  main="$widget_dir/main.py"

  if [[ -f "$main" ]]; then
    ln -sf "$main" "$BIN_DIR/$name"
    echo "  $name"
  fi

  status="$widget_dir/status"
  if [[ -f "$status" ]]; then
    ln -sf "$status" "$BIN_DIR/${name}-status"
    echo "  ${name}-status"
  fi
done

# Polkit rules (requires sudo)
polkit_src="$REPO_DIR/polkit/50-gtk-widgets-usb.rules"
polkit_dst="/etc/polkit-1/rules.d/50-gtk-widgets-usb.rules"
if [[ -f "$polkit_src" ]]; then
  if [[ ! -f "$polkit_dst" ]] || ! diff -q "$polkit_src" "$polkit_dst" &>/dev/null; then
    sudo cp "$polkit_src" "$polkit_dst"
    echo "  polkit: 50-gtk-widgets-usb.rules"
  fi
fi

echo "done"
