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

  # Extra CLI entry points (e.g. display/brightness.py -> display-brightness)
  for extra in "$widget_dir"/*.py; do
    [[ -x "$extra" && "$(basename "$extra")" != "main.py" ]] || continue
    cli="${name}-$(basename "$extra" .py)"
    ln -sf "$extra" "$BIN_DIR/$cli"
    echo "  $cli"
  done
done

# Privileged USB helper + polkit rule (requires sudo). The helper is the only
# program the rule authorises, so install it root-owned at a fixed path.
helper_src="$REPO_DIR/polkit/usb-helper"
helper_dst="/usr/lib/gtk-widgets/usb-helper"
if [[ -f "$helper_src" ]]; then
  if [[ ! -f "$helper_dst" ]] || ! diff -q "$helper_src" "$helper_dst" &>/dev/null; then
    sudo install -D -m 0755 -o root -g root "$helper_src" "$helper_dst"
    echo "  helper: $helper_dst"
  fi
fi

polkit_src="$REPO_DIR/polkit/50-gtk-widgets-usb.rules"
polkit_dst="/etc/polkit-1/rules.d/50-gtk-widgets-usb.rules"
if [[ -f "$polkit_src" ]]; then
  if [[ ! -f "$polkit_dst" ]] || ! diff -q "$polkit_src" "$polkit_dst" &>/dev/null; then
    sudo cp "$polkit_src" "$polkit_dst"
    echo "  polkit: 50-gtk-widgets-usb.rules"
  fi
fi

echo "done"
