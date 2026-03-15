#!/usr/bin/env python3
"""USB device manager popup — list, mount/unmount, format, write ISO."""

import json, os, subprocess, sys, threading
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib.widget_base import Gdk, Gtk, WidgetPopup, load_css

from gi.repository import GLib, Gio

CSS = load_css(os.path.join(_DIR, "style.css"))

FS_TYPES = ["vfat", "ext4", "ntfs", "exfat"]


def lsblk():
    """Return list of removable USB disk dicts from lsblk."""
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o",
             "NAME,SIZE,TYPE,MOUNTPOINT,RM,TRAN,VENDOR,MODEL,FSTYPE,LABEL"],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
    except Exception:
        return []
    devices = []
    for dev in data.get("blockdevices", []):
        if dev.get("tran") == "usb" and dev.get("rm"):
            devices.append(dev)
    return devices


def get_partitions(dev):
    """Return list of partition dicts for a device, or [dev] if unpartitioned."""
    children = dev.get("children", [])
    if children:
        return [p for p in children if p.get("type") == "part"]
    return [dev]


def is_mounted(part):
    return bool(part.get("mountpoint"))


def mount_part(part_name):
    """Mount a partition using mount. Returns mountpoint or error string."""
    dev = f"/dev/{part_name}"
    mountpoint = f"/run/media/{os.environ.get('USER', 'user')}/{part_name}"
    os.makedirs(mountpoint, exist_ok=True)
    result = subprocess.run(
        ["pkexec", "mount", dev, mountpoint],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return mountpoint
    return result.stderr.strip() or "Mount failed"


def unmount_part(part_name):
    """Unmount a partition. Returns True on success."""
    dev = f"/dev/{part_name}"
    result = subprocess.run(
        ["pkexec", "umount", dev],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def format_device(dev_name, fstype, label=None):
    """Format a device/partition. Returns (success, message)."""
    dev = f"/dev/{dev_name}"
    # Unmount all mounted partitions first
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,MOUNTPOINT", dev],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        for d in data.get("blockdevices", []):
            if d.get("mountpoint"):
                subprocess.run(["pkexec", "umount", f"/dev/{d['name']}"],
                               capture_output=True)
            for c in d.get("children", []):
                if c.get("mountpoint"):
                    subprocess.run(["pkexec", "umount", f"/dev/{c['name']}"],
                                   capture_output=True)
    except Exception:
        pass

    cmd = ["pkexec"]
    if fstype == "vfat":
        cmd += ["mkfs.vfat", "-F", "32"]
        if label:
            cmd += ["-n", label[:11].upper()]
    elif fstype == "ext4":
        cmd += ["mkfs.ext4", "-F"]
        if label:
            cmd += ["-L", label]
    elif fstype == "ntfs":
        cmd += ["mkfs.ntfs", "-f"]
        if label:
            cmd += ["-L", label]
    elif fstype == "exfat":
        cmd += ["mkfs.exfat"]
        if label:
            cmd += ["-L", label]
    cmd.append(dev)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return True, "Format complete"
    return False, result.stderr.strip() or "Format failed"


def write_iso(iso_path, dev_name, progress_cb=None):
    """Write ISO to device with dd. Calls progress_cb(bytes_written, total) periodically."""
    dev = f"/dev/{dev_name}"
    total = os.path.getsize(iso_path)

    # Unmount everything on the device
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,MOUNTPOINT", dev],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        for d in data.get("blockdevices", []):
            if d.get("mountpoint"):
                subprocess.run(["pkexec", "umount", f"/dev/{d['name']}"],
                               capture_output=True)
            for c in d.get("children", []):
                if c.get("mountpoint"):
                    subprocess.run(["pkexec", "umount", f"/dev/{c['name']}"],
                                   capture_output=True)
    except Exception:
        pass

    proc = subprocess.Popen(
        ["pkexec", "dd", f"if={iso_path}", f"of={dev}",
         "bs=4M", "conv=fdatasync", "status=progress"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    # dd writes progress to stderr
    written = 0
    for line in iter(proc.stderr.readline, b""):
        text = line.decode(errors="replace").strip()
        # Parse "123456789 bytes ..." lines
        if "bytes" in text and text[0].isdigit():
            try:
                written = int(text.split()[0])
                if progress_cb:
                    GLib.idle_add(progress_cb, written, total)
            except (ValueError, IndexError):
                pass

    proc.wait()
    if progress_cb:
        GLib.idle_add(progress_cb, total, total)
    return proc.returncode == 0


def refresh_waybar():
    subprocess.Popen(["pkill", "-RTMIN+12", "waybar"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class UsbPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.usb")
        self._monitor_id = 0

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

        # Title
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

        devices = lsblk()
        if not devices:
            empty = Gtk.Label(label="No USB devices detected")
            empty.add_css_class("usb-empty")
            self._container.append(empty)
            return

        for dev in devices:
            self._add_device(dev)

        # Status label
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

        # Device header
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
        name_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        info_box.append(name_label)
        detail = Gtk.Label(label=f"/dev/{dev_name}  {size}")
        detail.add_css_class("usb-device-detail")
        detail.set_halign(Gtk.Align.START)
        info_box.append(detail)
        header.append(info_box)

        self._container.append(header)

        # Partitions
        partitions = get_partitions(dev)
        for part in partitions:
            self._add_partition_row(dev, part)

        # Action buttons
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_row.add_css_class("usb-action-row")

        format_btn = Gtk.Button(label="Format")
        format_btn.add_css_class("usb-action-btn")
        format_btn.connect("clicked", lambda _, d=dev: self._show_format(d))
        btn_row.append(format_btn)

        iso_btn = Gtk.Button(label="Write ISO")
        iso_btn.add_css_class("usb-action-btn")
        iso_btn.connect("clicked", lambda _, d=dev: self._show_iso_picker(d))
        btn_row.append(iso_btn)

        eject_btn = Gtk.Button(label="Eject")
        eject_btn.add_css_class("usb-action-btn")
        eject_btn.add_css_class("usb-eject-btn")
        eject_btn.connect("clicked", lambda _, d=dev: self._eject(d))
        btn_row.append(eject_btn)

        self._container.append(btn_row)

    def _add_partition_row(self, dev, part):
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

            unmount_btn = Gtk.Button(label="Unmount")
            unmount_btn.add_css_class("usb-small-btn")
            unmount_btn.connect("clicked", lambda _, p=part_name: self._do_unmount(p))
            row.append(unmount_btn)
        else:
            mount_btn = Gtk.Button(label="Mount")
            mount_btn.add_css_class("usb-small-btn")
            mount_btn.connect("clicked", lambda _, p=part_name: self._do_mount(p))
            row.append(mount_btn)

        self._container.append(row)

    def _set_status(self, text, css_class=None):
        if not hasattr(self, "_status"):
            return
        self._status.set_text(text)
        self._status.remove_css_class("usb-status-ok")
        self._status.remove_css_class("usb-status-err")
        if css_class:
            self._status.add_css_class(css_class)

    def _do_mount(self, part_name):
        self._set_status("Mounting...")
        def task():
            result = mount_part(part_name)
            if result.startswith("/"):
                GLib.idle_add(self._after_action, f"Mounted at {result}", "usb-status-ok")
            else:
                GLib.idle_add(self._after_action, result, "usb-status-err")
        threading.Thread(target=task, daemon=True).start()

    def _do_unmount(self, part_name):
        self._set_status("Unmounting...")
        def task():
            ok = unmount_part(part_name)
            if ok:
                GLib.idle_add(self._after_action, "Unmounted", "usb-status-ok")
            else:
                GLib.idle_add(self._after_action, "Unmount failed", "usb-status-err")
        threading.Thread(target=task, daemon=True).start()

    def _eject(self, dev):
        dev_name = dev["name"]
        self._set_status("Ejecting...")
        def task():
            # Unmount all partitions
            for part in get_partitions(dev):
                if is_mounted(part):
                    subprocess.run(["pkexec", "umount", f"/dev/{part['name']}"],
                                   capture_output=True)
            # Power off the device
            dev_path = f"/dev/{dev_name}"
            # Get sysfs path for power-off
            try:
                sysfs = subprocess.run(
                    ["lsblk", "-ndo", "PATH", dev_path],
                    capture_output=True, text=True,
                ).stdout.strip()
                # Use eject command
                result = subprocess.run(
                    ["pkexec", "eject", dev_path],
                    capture_output=True, text=True,
                )
                if result.returncode == 0:
                    GLib.idle_add(self._after_action, "Ejected safely", "usb-status-ok")
                else:
                    GLib.idle_add(self._after_action,
                                  result.stderr.strip() or "Eject failed", "usb-status-err")
            except Exception as e:
                GLib.idle_add(self._after_action, str(e), "usb-status-err")
        threading.Thread(target=task, daemon=True).start()

    def _after_action(self, msg, css_class):
        refresh_waybar()
        self._build_ui()
        self._set_status(msg, css_class)
        return GLib.SOURCE_REMOVE

    # --- Format dialog ---

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

        # Filesystem picker
        fs_label = Gtk.Label(label="FILESYSTEM")
        fs_label.add_css_class("usb-field-label")
        fs_label.set_halign(Gtk.Align.START)
        self._container.append(fs_label)

        fs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._fs_buttons = {}
        self._selected_fs = "vfat"
        for fs in FS_TYPES:
            btn = Gtk.ToggleButton(label=fs)
            btn.add_css_class("usb-fs-btn")
            if fs == "vfat":
                btn.set_active(True)
                btn.add_css_class("usb-fs-active")
            btn.connect("toggled", self._on_fs_toggled, fs)
            fs_box.append(btn)
            self._fs_buttons[fs] = btn
        self._container.append(fs_box)

        # Label input
        label_label = Gtk.Label(label="LABEL (optional)")
        label_label.add_css_class("usb-field-label")
        label_label.set_halign(Gtk.Align.START)
        self._container.append(label_label)

        self._label_entry = Gtk.Entry()
        self._label_entry.add_css_class("usb-entry")
        self._label_entry.set_placeholder_text("MY_USB")
        self._container.append(self._label_entry)

        # Buttons
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

        # Status
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
            # Don't allow deselecting the current one
            btn.set_active(True)

    def _do_format(self, dev):
        dev_name = dev["name"]
        fstype = self._selected_fs
        label = self._label_entry.get_text().strip() or None
        self._set_status("Formatting...")

        def task():
            ok, msg = format_device(dev_name, fstype, label)
            css = "usb-status-ok" if ok else "usb-status-err"
            GLib.idle_add(self._after_action, msg, css)
        threading.Thread(target=task, daemon=True).start()

    # --- ISO writer ---

    def _show_iso_picker(self, dev):
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
            self.get_active_window(),
            None,
            lambda d, r, dev=dev: self._on_iso_selected(d, r, dev),
        )

    def _on_iso_selected(self, dialog, result, dev):
        try:
            gfile = dialog.open_finish(result)
            iso_path = gfile.get_path()
        except GLib.Error:
            return  # User cancelled

        self._show_iso_confirm(dev, iso_path)

    def _show_iso_confirm(self, dev, iso_path):
        self._clear_container()

        dev_name = dev["name"]
        vendor = (dev.get("vendor") or "").strip()
        model = (dev.get("model") or "").strip()
        display_name = f"{vendor} {model}".strip() or dev_name
        iso_name = os.path.basename(iso_path)
        iso_size = os.path.getsize(iso_path)
        iso_size_mb = iso_size / (1024 * 1024)

        title = Gtk.Label(label="Write ISO")
        title.add_css_class("usb-title")
        self._container.append(title)

        warning = Gtk.Label(label=f"All data on /dev/{dev_name} will be erased!")
        warning.add_css_class("usb-warning")
        self._container.append(warning)

        detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        detail_box.add_css_class("usb-iso-details")

        iso_label = Gtk.Label(label=f"  {iso_name}  ({iso_size_mb:.0f} MB)")
        iso_label.add_css_class("usb-iso-name")
        iso_label.set_halign(Gtk.Align.START)
        iso_label.set_ellipsize(3)
        detail_box.append(iso_label)

        target_label = Gtk.Label(label=f"󰗮  {display_name}  ({dev.get('size', '?')})")
        target_label.add_css_class("usb-iso-target")
        target_label.set_halign(Gtk.Align.START)
        detail_box.append(target_label)

        self._container.append(detail_box)

        # Buttons
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.add_css_class("usb-action-btn")
        cancel_btn.connect("clicked", lambda _: self._build_ui())
        btn_row.append(cancel_btn)

        write_btn = Gtk.Button(label="Write")
        write_btn.add_css_class("usb-danger-btn")
        write_btn.connect("clicked", lambda _, d=dev, p=iso_path: self._do_write_iso(d, p))
        btn_row.append(write_btn)

        self._container.append(btn_row)

    def _do_write_iso(self, dev, iso_path):
        self._clear_container()

        title = Gtk.Label(label="Writing ISO...")
        title.add_css_class("usb-title")
        self._container.append(title)

        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.add_css_class("usb-progress")
        self._container.append(self._progress_bar)

        self._progress_label = Gtk.Label(label="Starting...")
        self._progress_label.add_css_class("usb-progress-text")
        self._container.append(self._progress_label)

        self._status = Gtk.Label()
        self._status.add_css_class("usb-status")
        self._status.set_halign(Gtk.Align.START)
        self._container.append(self._status)

        def task():
            ok = write_iso(iso_path, dev["name"], progress_cb=self._update_progress)
            if ok:
                GLib.idle_add(self._after_action, "ISO written successfully", "usb-status-ok")
            else:
                GLib.idle_add(self._after_action, "Write failed", "usb-status-err")
        threading.Thread(target=task, daemon=True).start()

    def _update_progress(self, written, total):
        if total > 0:
            fraction = min(written / total, 1.0)
            self._progress_bar.set_fraction(fraction)
            written_mb = written / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self._progress_label.set_text(
                f"{written_mb:.0f} / {total_mb:.0f} MB  ({fraction * 100:.0f}%)")
        return GLib.SOURCE_REMOVE

    # --- USB hotplug monitor ---

    def _start_monitor(self):
        """Watch for USB add/remove events via udevadm monitor."""
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
                    # Debounce — only refresh after events settle
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
