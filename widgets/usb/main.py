#!/usr/bin/env python3
"""USB device manager popup — list, mount/unmount, format, write ISO."""

import json, os, re, shlex, subprocess, sys, threading
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib.widget_base import Gdk, Gtk, WidgetPopup, load_css

from gi.repository import GLib, Gio

CSS = load_css(os.path.join(_DIR, "style.css"))

FS_TYPES = ["exfat", "vfat", "ext4", "ntfs"]
_LABEL_RE = re.compile(r'^[A-Za-z0-9_-]+$')
_BUSY_DIR = "/tmp/.gtk-widgets-usb"


# --- State persistence ---

def _busy_path(dev_name):
    return os.path.join(_BUSY_DIR, dev_name)


def _save_busy(dev_name, text):
    os.makedirs(_BUSY_DIR, exist_ok=True)
    with open(_busy_path(dev_name), "w") as f:
        f.write(text)


def _clear_busy(dev_name):
    try:
        os.remove(_busy_path(dev_name))
    except FileNotFoundError:
        pass


def _load_busy(dev_name):
    try:
        with open(_busy_path(dev_name)) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


# --- Device helpers ---

def lsblk():
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o",
             "NAME,SIZE,TYPE,MOUNTPOINT,RM,TRAN,VENDOR,MODEL,FSTYPE,LABEL"],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
    except Exception:
        return []
    return [d for d in data.get("blockdevices", [])
            if d.get("tran") == "usb" and d.get("rm")]


def get_partitions(dev):
    children = dev.get("children", [])
    if children:
        return [p for p in children if p.get("type") == "part"]
    return [dev]


def _unmount_all(dev_name):
    dev = f"/dev/{dev_name}"
    cmds = []
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,MOUNTPOINT", dev],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        for d in data.get("blockdevices", []):
            if d.get("mountpoint"):
                cmds.append(f"umount /dev/{d['name']} 2>/dev/null")
            for c in d.get("children", []):
                if c.get("mountpoint"):
                    cmds.append(f"umount /dev/{c['name']} 2>/dev/null")
    except Exception:
        pass
    if cmds:
        subprocess.run(["pkexec", "bash", "-c", "; ".join(cmds)],
                       capture_output=True)


# --- Operations ---

def mount_part(part_name):
    dev = f"/dev/{part_name}"
    mountpoint = f"/run/media/{os.environ.get('USER', 'user')}/{part_name}"
    os.makedirs(mountpoint, exist_ok=True)
    result = subprocess.run(["pkexec", "mount", dev, mountpoint],
                            capture_output=True, text=True)
    if result.returncode == 0:
        return True, f"Mounted at {mountpoint}"
    return False, result.stderr.strip() or "Mount failed"


def unmount_part(part_name):
    result = subprocess.run(["pkexec", "umount", f"/dev/{part_name}"],
                            capture_output=True, text=True)
    if result.returncode == 0:
        return True, "Unmounted"
    return False, result.stderr.strip() or "Unmount failed"


def format_device(dev_name, fstype, label=None):
    dev = f"/dev/{dev_name}"
    part = f"{dev}1"
    _unmount_all(dev_name)

    mkfs = {"vfat": "mkfs.vfat -F 32", "ext4": "mkfs.ext4 -F",
            "ntfs": "mkfs.ntfs -f", "exfat": "mkfs.exfat"}.get(fstype)
    if not mkfs:
        return False, f"Unknown filesystem: {fstype}"

    if label:
        if not _LABEL_RE.match(label):
            return False, "Label may only contain letters, numbers, - and _"
        lbl = label[:11].upper() if fstype == "vfat" else label
        flag = "-n" if fstype == "vfat" else "-L"
        mkfs += f" {flag} {lbl}"

    script = f"wipefs -af {dev} && echo 'type=83' | sfdisk {dev} && {mkfs} {part}"
    result = subprocess.run(["pkexec", "bash", "-c", script],
                            capture_output=True, text=True)
    if result.returncode == 0:
        return True, "Format complete"
    return False, result.stderr.strip() or "Format failed"


def write_iso(iso_path, dev_name):
    dev = f"/dev/{dev_name}"
    _unmount_all(dev_name)
    script = f"dd if={shlex.quote(iso_path)} of={dev} bs=4M conv=fdatasync status=none"
    result = subprocess.run(["pkexec", "bash", "-c", script],
                            capture_output=True, text=True)
    if result.returncode == 0:
        return True, "ISO written successfully"
    return False, result.stderr.strip() or "Write failed"


def eject_device(dev_name):
    _unmount_all(dev_name)
    result = subprocess.run(["pkexec", "bash", "-c", f"eject /dev/{dev_name}"],
                            capture_output=True, text=True)
    if result.returncode == 0:
        return True, "Ejected safely"
    return False, result.stderr.strip() or "Eject failed"


def refresh_waybar():
    subprocess.Popen(["pkill", "-RTMIN+12", "waybar"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --- Widget ---

class UsbPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.usb")
        self._monitor_id = 0
        self._busy = {}
        self._status = None

    def build_ui(self):
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._container.add_css_class("usb-container")
        self._build_ui()
        self._start_monitor()
        return self._container

    def _clear_container(self):
        while child := self._container.get_first_child():
            self._container.remove(child)

    def _build_ui(self):
        self._clear_container()

        devices = lsblk()

        # Restore busy state from disk for devices we don't know about
        for dev in devices:
            name = dev["name"]
            if name not in self._busy:
                text = _load_busy(name)
                if text:
                    self._busy[name] = text

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="USB Devices")
        title.add_css_class("usb-title")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        title_row.append(title)

        refresh_btn = Gtk.Button(label="󰑐")
        refresh_btn.add_css_class("usb-refresh-btn")
        refresh_btn.set_tooltip_text("Refresh")
        refresh_btn.connect("clicked", lambda _: self._build_ui())
        title_row.append(refresh_btn)
        self._container.append(title_row)

        if not devices:
            empty = Gtk.Label(label="No USB devices detected")
            empty.add_css_class("usb-empty")
            self._container.append(empty)
            self._status = None
            return

        for dev in devices:
            self._add_device(dev)

        self._status = Gtk.Label()
        self._status.add_css_class("usb-status")
        self._status.set_halign(Gtk.Align.START)
        self._container.append(self._status)

    def _add_device(self, dev):
        dev_name = dev["name"]
        vendor = (dev.get("vendor") or "").strip()
        model = (dev.get("model") or "").strip()
        display_name = f"{vendor} {model}".strip() or dev_name
        size = dev.get("size", "?")
        busy = dev_name in self._busy

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.add_css_class("usb-device-header")

        icon = Gtk.Label(label="󰗮")
        icon.add_css_class("usb-device-icon")
        header.append(icon)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)
        name_label = Gtk.Label(label=display_name)
        name_label.add_css_class("usb-device-name")
        name_label.set_halign(Gtk.Align.START)
        name_label.set_ellipsize(3)
        info_box.append(name_label)

        detail_text = self._busy[dev_name] if busy else f"/dev/{dev_name}  {size}"
        detail = Gtk.Label(label=detail_text)
        detail.add_css_class("usb-device-detail")
        if busy:
            detail.add_css_class("usb-device-busy")
        detail.set_halign(Gtk.Align.START)
        info_box.append(detail)
        header.append(info_box)
        self._container.append(header)

        for part in get_partitions(dev):
            self._add_partition_row(part, busy)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_row.add_css_class("usb-action-row")

        for label, css, cb in [
            ("Format", "usb-action-btn", lambda _, d=dev: self._show_format(d)),
            ("Write ISO", "usb-action-btn", lambda _, d=dev: self._pick_iso(d)),
            ("Eject", "usb-eject-btn", lambda _, d=dev: self._do_eject(d)),
        ]:
            btn = Gtk.Button(label=label)
            btn.add_css_class("usb-action-btn")
            if css != "usb-action-btn":
                btn.add_css_class(css)
            btn.set_sensitive(not busy)
            btn.connect("clicked", cb)
            btn_row.append(btn)

        self._container.append(btn_row)

    def _add_partition_row(self, part, busy):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("usb-partition-row")

        fstype = part.get("fstype") or "unknown"
        label = part.get("label") or ""
        mountpoint = part.get("mountpoint") or ""
        mounted = bool(mountpoint)
        part_name = part["name"]
        size = part.get("size", "?")

        label_text = f"{label}  " if label else ""
        info_text = f"{label_text}{fstype}  {size}"
        if mounted:
            info_text += f"  {mountpoint}"

        info = Gtk.Label(label=info_text)
        info.add_css_class("usb-partition-info")
        info.set_hexpand(True)
        info.set_halign(Gtk.Align.START)
        info.set_ellipsize(3)
        row.append(info)

        if mounted:
            dot = Gtk.Label(label="")
            dot.add_css_class("usb-mounted-dot")
            row.append(dot)
            btn = Gtk.Button(label="Unmount")
            btn.add_css_class("usb-small-btn")
            btn.set_sensitive(not busy)
            btn.connect("clicked", lambda _, p=part_name: self._run_task(
                lambda: unmount_part(p)))
            row.append(btn)
        else:
            btn = Gtk.Button(label="Mount")
            btn.add_css_class("usb-small-btn")
            btn.set_sensitive(not busy)
            btn.connect("clicked", lambda _, p=part_name: self._run_task(
                lambda: mount_part(p)))
            row.append(btn)

        self._container.append(row)

    # --- Task runner ---

    def _run_task(self, task_fn, dev_name=None, busy_text=None):
        if dev_name and busy_text:
            self._busy[dev_name] = busy_text
            _save_busy(dev_name, busy_text)
            self._build_ui()

        def worker():
            ok, msg = task_fn()
            def done():
                if dev_name:
                    self._busy.pop(dev_name, None)
                    _clear_busy(dev_name)
                refresh_waybar()
                self._build_ui()
                self._set_status(msg, "usb-status-ok" if ok else "usb-status-err")
                return GLib.SOURCE_REMOVE
            GLib.idle_add(done)

        threading.Thread(target=worker, daemon=True).start()

    def _set_status(self, text, css_class=None):
        if not self._status:
            return
        self._status.set_text(text)
        self._status.remove_css_class("usb-status-ok")
        self._status.remove_css_class("usb-status-err")
        if css_class:
            self._status.add_css_class(css_class)

    # --- Actions ---

    def _do_eject(self, dev):
        self._run_task(lambda: eject_device(dev["name"]),
                       dev["name"], "Ejecting...")

    def _pick_iso(self, dev):
        win = self.get_active_window()
        if win:
            win.set_visible(False)

        dialog = Gtk.FileDialog()
        dialog.set_title("Select ISO file")
        ff = Gtk.FileFilter()
        ff.set_name("ISO images")
        ff.add_pattern("*.iso")
        ff.add_pattern("*.img")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(ff)
        dialog.set_filters(filters)
        dialog.open(
            win, None,
            lambda d, r, dev=dev, w=win: self._on_iso_picked(d, r, dev, w),
        )

    def _on_iso_picked(self, dialog, result, dev, win):
        try:
            iso_path = dialog.open_finish(result).get_path()
        except GLib.Error:
            if win:
                win.set_visible(True)
            return
        if win:
            win.set_visible(True)
        iso_name = os.path.basename(iso_path)
        self._run_task(lambda: write_iso(iso_path, dev["name"]),
                       dev["name"], f"Writing {iso_name}...")

    # --- Format ---

    def _show_format(self, dev):
        self._clear_container()

        dev_name = dev["name"]
        vendor = (dev.get("vendor") or "").strip()
        model = (dev.get("model") or "").strip()
        display_name = f"{vendor} {model}".strip() or dev_name

        title = Gtk.Label(label=f"Format {display_name}")
        title.add_css_class("usb-title")
        self._container.append(title)

        warning = Gtk.Label(label=f"All data on /dev/{dev_name} will be erased!")
        warning.add_css_class("usb-warning")
        self._container.append(warning)

        fs_label = Gtk.Label(label="FILESYSTEM")
        fs_label.add_css_class("usb-field-label")
        fs_label.set_halign(Gtk.Align.START)
        self._container.append(fs_label)

        fs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._fs_buttons = {}
        self._selected_fs = "exfat"
        for fs in FS_TYPES:
            btn = Gtk.ToggleButton(label=fs)
            btn.add_css_class("usb-fs-btn")
            if fs == "exfat":
                btn.set_active(True)
                btn.add_css_class("usb-fs-active")
            btn.connect("toggled", self._on_fs_toggled, fs)
            fs_box.append(btn)
            self._fs_buttons[fs] = btn
        self._container.append(fs_box)

        label_label = Gtk.Label(label="LABEL (optional)")
        label_label.add_css_class("usb-field-label")
        label_label.set_halign(Gtk.Align.START)
        self._container.append(label_label)

        self._label_entry = Gtk.Entry()
        self._label_entry.add_css_class("usb-entry")
        self._label_entry.set_placeholder_text("MY_USB")
        self._container.append(self._label_entry)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.add_css_class("usb-action-btn")
        cancel_btn.connect("clicked", lambda _: self._build_ui())
        btn_row.append(cancel_btn)

        confirm_btn = Gtk.Button(label="Format")
        confirm_btn.add_css_class("usb-danger-btn")
        confirm_btn.connect("clicked", lambda _, d=dev: self._do_format(d))
        btn_row.append(confirm_btn)

        self._container.append(btn_row)

        self._status = Gtk.Label()
        self._status.add_css_class("usb-status")
        self._status.set_halign(Gtk.Align.START)
        self._container.append(self._status)

    def _on_fs_toggled(self, btn, fs):
        if btn.get_active():
            self._selected_fs = fs
            for name, b in self._fs_buttons.items():
                if name != fs:
                    b.set_active(False)
                    b.remove_css_class("usb-fs-active")
            btn.add_css_class("usb-fs-active")
        elif self._selected_fs == fs:
            btn.set_active(True)

    def _do_format(self, dev):
        dev_name = dev["name"]
        fstype = self._selected_fs
        label = self._label_entry.get_text().strip() or None
        self._run_task(lambda: format_device(dev_name, fstype, label),
                       dev_name, "Formatting...")

    # --- USB hotplug monitor ---

    def _start_monitor(self):
        try:
            self._udev_proc = subprocess.Popen(
                ["udevadm", "monitor", "--subsystem-match=block", "--udev"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return

        def watch():
            for line in iter(self._udev_proc.stdout.readline, b""):
                text = line.decode(errors="replace")
                if "add" in text or "remove" in text:
                    if self._monitor_id:
                        GLib.source_remove(self._monitor_id)
                    self._monitor_id = GLib.timeout_add(500, self._on_usb_change)

        threading.Thread(target=watch, daemon=True).start()

    def _on_usb_change(self):
        self._monitor_id = 0
        refresh_waybar()
        self._build_ui()
        return GLib.SOURCE_REMOVE

    def _on_key(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q):
            self.quit()
            return True
        return False

    def do_shutdown(self):
        if hasattr(self, "_udev_proc") and self._udev_proc.poll() is None:
            self._udev_proc.terminate()
        Gtk.Application.do_shutdown(self)


if __name__ == "__main__":
    UsbPopup.CSS = CSS
    UsbPopup().run()
