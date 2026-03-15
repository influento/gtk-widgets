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


def _read_sectors(dev_name):
    """Read cumulative sectors written from sysfs."""
    try:
        with open(f"/sys/block/{dev_name}/stat") as f:
            return int(f.read().split()[6])
    except (FileNotFoundError, IndexError, ValueError):
        return 0


def _save_busy(dev_name, text, total=0):
    os.makedirs(_BUSY_DIR, exist_ok=True)
    data = {"text": text, "total": total}
    if total:
        data["start_sectors"] = _read_sectors(dev_name)
    with open(_busy_path(dev_name), "w") as f:
        json.dump(data, f)


def _clear_busy(dev_name):
    try:
        os.remove(_busy_path(dev_name))
    except FileNotFoundError:
        pass


def _is_device_busy(dev_name):
    try:
        result = subprocess.run(["pgrep", "-fa", f"/dev/{dev_name}"],
                                capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def _load_busy(dev_name):
    """Return (text, total, start_sectors) or (None, 0, 0)."""
    try:
        with open(_busy_path(dev_name)) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None, 0, 0
    if not _is_device_busy(dev_name):
        _clear_busy(dev_name)
        return None, 0, 0
    return data.get("text"), data.get("total", 0), data.get("start_sectors", 0)


def _get_progress_text(dev_name, total, start_sectors):
    """Calculate progress from sysfs sectors written."""
    if not total or not start_sectors:
        return None
    current = _read_sectors(dev_name)
    written_bytes = (current - start_sectors) * 512
    if written_bytes < 0:
        return None
    written_mb = written_bytes // (1024 * 1024)
    total_mb = total // (1024 * 1024)
    pct = min(written_bytes * 100 // total, 100)
    return f"{written_mb}/{total_mb} MB  {pct}%"


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


def refresh_waybar():
    subprocess.Popen(["pkill", "-RTMIN+12", "waybar"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --- Widget ---

class UsbPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.usb")
        self._monitor_id = 0
        self._poll_id = 0
        self._busy = {}
        self._busy_meta = {}   # dev_name -> (total, start_sectors)
        self._busy_labels = {} # dev_name -> Gtk.Label

    def build_ui(self):
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._container.add_css_class("usb-container")
        self._build_ui()
        self._start_monitor()
        self._start_poll()
        return self._container

    def _clear_container(self):
        while child := self._container.get_first_child():
            self._container.remove(child)

    def _build_ui(self):
        self._clear_container()
        self._busy_labels = {}

        devices = lsblk()

        # Restore busy state from disk for devices we don't know about
        for dev in devices:
            name = dev["name"]
            if name not in self._busy:
                text, total, start = _load_busy(name)
                if text:
                    self._busy[name] = text
                    self._busy_meta[name] = (total, start)

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
            return

        for dev in devices:
            self._add_device(dev)

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

        detail = Gtk.Label(label=f"/dev/{dev_name}  {size}")
        detail.add_css_class("usb-device-detail")
        detail.set_halign(Gtk.Align.START)
        info_box.append(detail)

        if busy:
            busy_label = Gtk.Label(label=self._busy[dev_name])
            busy_label.add_css_class("usb-device-busy")
            busy_label.set_halign(Gtk.Align.START)
            busy_label.set_ellipsize(3)
            info_box.append(busy_label)

            progress_label = Gtk.Label(label="0%")
            progress_label.add_css_class("usb-device-progress")
            progress_label.set_halign(Gtk.Align.START)
            info_box.append(progress_label)
            self._busy_labels[dev_name] = progress_label

        # Partition info
        children = dev.get("children", [])
        parts = [p for p in children if p.get("type") == "part"] if children else []
        if parts:
            for p in parts:
                fstype = p.get("fstype") or ""
                plabel = p.get("label") or ""
                psize = p.get("size", "")
                parts_text = "  ".join(x for x in [plabel, fstype, psize] if x)
                if parts_text:
                    pl = Gtk.Label(label=parts_text)
                    pl.add_css_class("usb-partition-info")
                    pl.set_halign(Gtk.Align.START)
                    info_box.append(pl)

        header.append(info_box)
        self._container.append(header)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_row.add_css_class("usb-action-row")

        format_btn = Gtk.Button(label="Format")
        format_btn.add_css_class("usb-action-btn")
        format_btn.set_sensitive(not busy)
        format_btn.connect("clicked", lambda _, d=dev: self._show_format(d))
        btn_row.append(format_btn)

        iso_btn = Gtk.Button(label="Write ISO")
        iso_btn.add_css_class("usb-action-btn")
        iso_btn.set_sensitive(not busy)
        iso_btn.connect("clicked", lambda _, d=dev: self._pick_iso(d))
        btn_row.append(iso_btn)

        self._container.append(btn_row)

    # --- Task runner ---

    def _run_task(self, task_fn, dev_name=None, busy_text=None, total=0):
        if dev_name and busy_text:
            self._busy[dev_name] = busy_text
            _save_busy(dev_name, busy_text, total)
            if total:
                self._busy_meta[dev_name] = (total, _read_sectors(dev_name))
            self._build_ui()

        def worker():
            ok, msg = task_fn()
            def done():
                if dev_name:
                    self._busy.pop(dev_name, None)
                    self._busy_meta.pop(dev_name, None)
                    _clear_busy(dev_name)
                refresh_waybar()
                self._build_ui()
                return GLib.SOURCE_REMOVE
            GLib.idle_add(done)

        threading.Thread(target=worker, daemon=True).start()

    # --- Actions ---

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
        dev_name = dev["name"]
        total = os.path.getsize(iso_path)
        self._run_task(lambda: write_iso(iso_path, dev_name),
                       dev_name, f"Writing {iso_name}...", total)

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

    def _start_poll(self):
        if not self._poll_id:
            self._poll_id = GLib.timeout_add(1000, self._poll_busy)

    def _poll_busy(self):
        changed = False
        for dev_name in list(self._busy):
            meta = self._busy_meta.get(dev_name)
            if meta:
                total, start = meta
                progress = _get_progress_text(dev_name, total, start)
                if progress:
                    label = self._busy_labels.get(dev_name)
                    if label:
                        label.set_text(progress)
            # Check if task finished
            if not _is_device_busy(dev_name):
                self._busy.pop(dev_name, None)
                self._busy_meta.pop(dev_name, None)
                _clear_busy(dev_name)
                changed = True
        if changed:
            self._build_ui()
        return GLib.SOURCE_CONTINUE

    def _on_key(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q):
            self.quit()
            return True
        return False

    def do_shutdown(self):
        if self._poll_id:
            GLib.source_remove(self._poll_id)
            self._poll_id = 0
        if hasattr(self, "_udev_proc") and self._udev_proc.poll() is None:
            self._udev_proc.terminate()
        Gtk.Application.do_shutdown(self)


if __name__ == "__main__":
    UsbPopup.CSS = CSS
    UsbPopup().run()
