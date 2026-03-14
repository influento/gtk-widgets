#!/usr/bin/env python3
"""Bluetooth popup — GTK4 widget for managing Bluetooth devices."""

import os, subprocess, sys, threading
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib.widget_base import Gdk, Gtk, WidgetPopup, load_css

from gi.repository import GLib

CSS = load_css(os.path.join(_DIR, "style.css"))

ICON_MAP = {
    "audio-headset": "󰋋",
    "audio-headphones": "󰋋",
    "audio-card": "󰓃",
    "input-keyboard": "󰌌",
    "input-mouse": "󰍽",
    "input-gaming": "󰊗",
    "input-tablet": "󰓶",
    "phone": "󰏲",
    "computer": "󰟀",
    "camera-photo": "󰄀",
    "printer": "󰐪",
}
DEFAULT_ICON = "󰂱"


def bt_run(*args, timeout=5, input_text=None):
    """Run a bluetoothctl command and return stdout."""
    try:
        result = subprocess.run(
            ["bluetoothctl", *args],
            capture_output=True, text=True, timeout=timeout,
            input=input_text,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def has_controller():
    return "No default controller available" not in bt_run("show")


def is_kernel_stale():
    running = os.uname().release
    return not os.path.isdir(f"/lib/modules/{running}")


def is_powered():
    return "Powered: yes" in bt_run("show")


def get_device_icon(mac):
    """Get icon string from bluetoothctl info Icon field."""
    info = bt_run("info", mac)
    for line in info.splitlines():
        line = line.strip()
        if line.startswith("Icon:"):
            icon_type = line.split(":", 1)[1].strip()
            return ICON_MAP.get(icon_type, DEFAULT_ICON)
    return DEFAULT_ICON


def get_device_name(mac):
    """Get device name from bluetoothctl info."""
    info = bt_run("info", mac)
    for line in info.splitlines():
        line = line.strip()
        if line.startswith("Alias:"):
            return line.split(":", 1)[1].strip()
    return mac


def parse_device_list(output):
    """Parse 'Device XX:XX:XX:XX:XX:XX Name' lines into [(mac, name)]."""
    devices = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Device "):
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                devices.append((parts[1], parts[2]))
            elif len(parts) == 2:
                devices.append((parts[1], parts[1]))
    return devices


def get_connected():
    return parse_device_list(bt_run("devices", "Connected"))


def get_paired():
    return parse_device_list(bt_run("devices", "Paired"))


def get_discovered():
    """Get discovered devices that are not paired."""
    all_devices = parse_device_list(bt_run("devices"))
    paired_macs = {mac for mac, _ in get_paired()}
    return [(mac, name) for mac, name in all_devices if mac not in paired_macs]


def refresh_waybar():
    subprocess.Popen(["pkill", "-RTMIN+10", "waybar"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class BluetoothPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.bluetooth")
        self._scan_process = None
        self._scan_timeout = 0
        self._scanning = False

    def build_ui(self):
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._container.add_css_class("bt-container")
        self._build_ui()
        return self._container

    def _clear_container(self):
        while child := self._container.get_first_child():
            self._container.remove(child)

    def _build_ui(self):
        self._clear_container()

        # Title row
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="Bluetooth")
        title.add_css_class("bt-title")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        title_row.append(title)

        if not has_controller():
            self._container.append(title_row)
            error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            error_box.set_halign(Gtk.Align.CENTER)
            icon = Gtk.Label(label="󰂲")
            icon.add_css_class("bt-error-icon")
            error_box.append(icon)
            msg = Gtk.Label(label="No controller available")
            msg.add_css_class("bt-error-msg")
            error_box.append(msg)
            if is_kernel_stale():
                hint_text = "Kernel updated — reboot to restore bluetooth"
            else:
                hint_text = "Check adapter or restart bluetooth service"
            hint = Gtk.Label(label=hint_text)
            hint.add_css_class("bt-error-hint")
            error_box.append(hint)
            self._container.append(error_box)
            return

        powered = is_powered()
        power_btn = Gtk.Button(label="󰂯" if powered else "󰂲")
        power_btn.add_css_class("bt-power-btn")
        power_btn.add_css_class("bt-power-on" if powered else "bt-power-off")
        power_btn.set_tooltip_text("Power off" if powered else "Power on")
        power_btn.connect("clicked", self._on_power_toggle)
        title_row.append(power_btn)

        self._container.append(title_row)

        if not powered:
            msg = Gtk.Label(label="Bluetooth is powered off")
            msg.add_css_class("bt-off-msg")
            self._container.append(msg)
            return

        # Connected section
        connected = get_connected()
        if connected:
            self._add_section("Connected")
            for mac, name in connected:
                self._add_device_row(mac, name, [("Disconnect", self._on_disconnect)])

        # Paired (not connected) section
        paired = get_paired()
        connected_macs = {mac for mac, _ in connected}
        paired_only = [(mac, name) for mac, name in paired if mac not in connected_macs]
        if paired_only:
            self._add_section("Paired")
            for mac, name in paired_only:
                self._add_device_row(mac, name, [("Connect", self._on_connect), ("Remove", self._on_remove)])

        # Separator + scan button
        sep = Gtk.Separator()
        sep.add_css_class("bt-separator")
        self._container.append(sep)

        self._scan_btn = Gtk.Button(label="Scan for devices")
        self._scan_btn.add_css_class("bt-scan-btn")
        self._scan_btn.connect("clicked", self._on_scan)
        self._container.append(self._scan_btn)

        # Nearby section (populated during scan)
        self._nearby_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._container.append(self._nearby_box)

        # Status label
        self._status = Gtk.Label()
        self._status.add_css_class("bt-status")
        self._status.set_halign(Gtk.Align.START)
        self._container.append(self._status)

    def _add_section(self, label):
        section = Gtk.Label(label=label)
        section.add_css_class("bt-section")
        section.set_halign(Gtk.Align.START)
        self._container.append(section)

    def _add_device_row(self, mac, name, actions, parent=None):
        target = parent if parent else self._container
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("bt-device-row")

        icon_label = Gtk.Label(label=get_device_icon(mac))
        icon_label.add_css_class("bt-device-icon")
        row.append(icon_label)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)
        name_label = Gtk.Label(label=name)
        name_label.add_css_class("bt-device-name")
        name_label.set_halign(Gtk.Align.START)
        info_box.append(name_label)
        mac_label = Gtk.Label(label=mac)
        mac_label.add_css_class("bt-device-mac")
        mac_label.set_halign(Gtk.Align.START)
        info_box.append(mac_label)
        row.append(info_box)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_box.set_valign(Gtk.Align.CENTER)
        for label, callback in actions:
            btn = Gtk.Button(label=label)
            btn.add_css_class("bt-action-btn")
            btn.connect("clicked", lambda _, m=mac, cb=callback: cb(m))
            btn_box.append(btn)
        row.append(btn_box)

        target.append(row)

    def _set_status(self, text, css_class=None):
        self._status.set_text(text)
        self._status.remove_css_class("bt-status-ok")
        self._status.remove_css_class("bt-status-err")
        if css_class:
            self._status.add_css_class(css_class)

    def _on_power_toggle(self, _btn):
        action = "off" if is_powered() else "on"
        bt_run("power", action)
        refresh_waybar()
        self._build_ui()

    def _on_disconnect(self, mac):
        self._set_status("Disconnecting...")
        def task():
            bt_run("disconnect", mac)
            GLib.idle_add(self._after_action, "Disconnected", "bt-status-ok")
        threading.Thread(target=task, daemon=True).start()

    def _on_remove(self, mac):
        self._set_status("Removing...")
        def task():
            bt_run("disconnect", mac)
            bt_run("untrust", mac)
            bt_run("remove", mac)
            GLib.idle_add(self._after_action, "Removed", "bt-status-ok")
        threading.Thread(target=task, daemon=True).start()

    def _on_connect(self, mac):
        self._set_status("Connecting...")
        def task():
            result = bt_run("connect", mac, timeout=10)
            if "Connection successful" in result:
                GLib.idle_add(self._after_action, "Connected", "bt-status-ok")
            else:
                GLib.idle_add(self._after_action, "Connection failed", "bt-status-err")
        threading.Thread(target=task, daemon=True).start()

    def _on_pair(self, mac):
        self._set_status("Pairing...")
        def task():
            result = bt_run("pair", mac, timeout=15, input_text="yes\n")
            if "Pairing successful" in result or "AlreadyExists" in result:
                bt_run("trust", mac)
                connect_result = bt_run("connect", mac, timeout=10)
                if "Connection successful" in connect_result:
                    GLib.idle_add(self._after_action, "Paired and connected", "bt-status-ok")
                else:
                    GLib.idle_add(self._after_action, "Paired (connect failed)", "bt-status-err")
            else:
                GLib.idle_add(self._after_action, "Pairing failed", "bt-status-err")
        threading.Thread(target=task, daemon=True).start()

    def _after_action(self, msg, css_class):
        refresh_waybar()
        self._build_ui()
        self._set_status(msg, css_class)
        return GLib.SOURCE_REMOVE

    def _on_scan(self, _btn):
        self._scan_btn.set_label("Scanning...")
        self._scan_btn.set_sensitive(False)
        self._scanning = True

        def scan_task():
            try:
                self._scan_process = subprocess.Popen(
                    ["bluetoothctl", "--timeout", "10", "scan", "on"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self._scan_process.wait()
            except FileNotFoundError:
                GLib.idle_add(self._set_status, "bluetoothctl not found", "bt-status-err")
            finally:
                GLib.idle_add(self._stop_scan)
        threading.Thread(target=scan_task, daemon=True).start()

        self._scan_timeout = GLib.timeout_add(2000, self._refresh_nearby)

    def _refresh_nearby(self):
        while child := self._nearby_box.get_first_child():
            self._nearby_box.remove(child)

        nearby = get_discovered()
        if nearby:
            section = Gtk.Label(label="Nearby")
            section.add_css_class("bt-section")
            section.set_halign(Gtk.Align.START)
            self._nearby_box.append(section)
            for mac, name in nearby:
                self._add_device_row(mac, name, [("Pair", self._on_pair)], parent=self._nearby_box)
        return GLib.SOURCE_CONTINUE

    def _stop_scan(self):
        self._scanning = False
        self._kill_scan()
        if self._scan_timeout:
            GLib.source_remove(self._scan_timeout)
            self._scan_timeout = 0
        self._refresh_nearby()
        self._scan_btn.set_label("Scan for devices")
        self._scan_btn.set_sensitive(True)
        return GLib.SOURCE_REMOVE

    def _kill_scan(self):
        if self._scan_process and self._scan_process.poll() is None:
            self._scan_process.terminate()
            self._scan_process = None
        bt_run("scan", "off")

    def do_shutdown(self):
        self._scanning = False
        self._kill_scan()
        if self._scan_timeout:
            GLib.source_remove(self._scan_timeout)
            self._scan_timeout = 0
        Gtk.Application.do_shutdown(self)

    def _on_key(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q):
            self.quit()
            return True
        return False


if __name__ == "__main__":
    BluetoothPopup.CSS = CSS
    BluetoothPopup().run()
