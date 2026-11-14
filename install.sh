#!/usr/bin/env bash
set -euo pipefail

# Install gtk-widgets: launchers for the commands, the bash status scripts and
# widget-toggle into ~/.local/bin;
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

# Commands: a launcher per [project.scripts] entry in pyproject.toml. Each runs
# on the system python3 with this checkout's src/ on its path (no venv needed)
src_dir="$REPO_DIR/src"
while read -r cli module func; do
  tmp="$(mktemp "$BIN_DIR/.$cli.XXXXXX")"
  cat > "$tmp" <<EOF
#!/usr/bin/env python3
# Written by gtk-widgets' install.sh
import sys
sys.path.insert(0, "$src_dir")
from $module import $func
sys.exit($func())
EOF
  chmod 0755 "$tmp"
  mv -f "$tmp" "$BIN_DIR/$cli"  # replaces an older symlink, never writes through it
  echo "  $cli"
done < <(python3 -I -c '
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    scripts = tomllib.load(f)["project"]["scripts"]
for cli, target in scripts.items():
    module, func = target.split(":")
    print(cli, module, func)
' "$REPO_DIR/pyproject.toml")

# The bash status scripts, as <widget>-status
for status in "$src_dir"/gtk_widgets/widgets/*/status; do
  name="$(basename "$(dirname "$status")")-status"
  ln -sfn "$status" "$BIN_DIR/$name"
  echo "  $name"
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
