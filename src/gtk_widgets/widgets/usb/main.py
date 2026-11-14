#!/usr/bin/env python3
"""USB device manager popup — list, mount, format, write ISO."""

import contextlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import IO, override

from gi.repository import Gio, GLib, Pango

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.lib.ui.background import in_background
from gtk_widgets.lib.ui.copy_label import CopyLabel, copyable
from gtk_widgets.lib.ui.widget_base import Gtk, WidgetPopup
from gtk_widgets.widgets.usb.parse import (
    Busy,
    Device,
    Partition,
    parse_busy,
    parse_lsblk,
)

FS_TYPES = ["exfat", "vfat", "ext4", "ntfs"]
_LABEL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
HELPER = "/usr/lib/gtk-widgets/usb-helper"
# Partition-table types macOS/Windows need to open each filesystem (mirrors
# usb-helper's fix-type). Linux ignores them, so a wrong one only shows elsewhere.
_MBR_OK = {"vfat": {0x6, 0xB, 0xC, 0xE}, "exfat": {0x7}, "ntfs": {0x7}}
_GPT_BASIC_DATA = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"
_BUSY_DIR = (
    Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir())) / "gtk-widgets-usb"
)
_SECTOR = 512  # bytes per sector in /sys/block/<dev>/stat
_MB = 1024 * 1024
_SECTORS_WRITTEN = 6  # field index in /sys/block/<dev>/stat


class TaskFailed(RuntimeError):
    """A device task failed; the message is shown as it is."""


# --- State persistence ---


def _busy_path(dev_name: str) -> Path:
    return _BUSY_DIR / dev_name


def _read_sectors(dev_name: str) -> int:
    """Read cumulative sectors written from sysfs."""
    try:
        text = Path(f"/sys/block/{dev_name}/stat").read_text()
        return int(text.split()[_SECTORS_WRITTEN])
    except FileNotFoundError, IndexError, ValueError:
        return 0


def _save_busy(dev_name: str, text: str, total: int = 0) -> None:
    _BUSY_DIR.mkdir(exist_ok=True, parents=True)
    data = {"text": text, "total": total}
    if total:
        data["start_sectors"] = _read_sectors(dev_name)
    _busy_path(dev_name).write_text(json.dumps(data))


def _clear_busy(dev_name: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        _busy_path(dev_name).unlink()


def _is_device_busy(dev_name: str) -> bool:
    # Match /dev/<name> (or a partition like /dev/<name>1) only when it appears
    # as a real device argument — preceded by start/space/'=' and followed by an
    # optional partition number then space/end. The old `pgrep -f /dev/sdb` did a
    # bare substring match, so it also matched siblings like /dev/sdba and
    # unrelated paths such as `vim ~/dev/sdb.txt`, falsely marking it busy.
    pattern = rf"(^|[[:space:]=])/dev/{dev_name}([0-9]+)?([[:space:]]|$)"
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern], capture_output=True, text=True, check=False
        )
    except OSError:
        return False
    return result.returncode == 0


def _load_busy(dev_name: str) -> Busy | None:
    """The saved task on a device while a process still uses it."""
    try:
        data: object = json.loads(_busy_path(dev_name).read_text())
    except FileNotFoundError, json.JSONDecodeError:
        return None
    if not _is_device_busy(dev_name):
        _clear_busy(dev_name)
        return None
    match parse_busy(data):
        case ParseError():
            return None
        case busy:
            return busy


def _get_progress_text(dev_name: str, total: int, start_sectors: int) -> str | None:
    """Calculate progress from sysfs sectors written."""
    if not total or not start_sectors:
        return None
    current = _read_sectors(dev_name)
    written_bytes = (current - start_sectors) * _SECTOR
    if written_bytes < 0:
        return None
    written_mb = written_bytes // _MB
    total_mb = total // _MB
    pct = min(written_bytes * 100 // total, 100)
    return f"{written_mb}/{total_mb} MB  {pct}%"


# --- Device helpers ---


def lsblk() -> list[Device]:
    """The removable USB disks; none when lsblk fails or answers oddly."""
    try:
        result = subprocess.run(
            [
                "lsblk",
                "-J",
                "-o",
                "NAME,SIZE,TYPE,MOUNTPOINT,RM,TRAN,VENDOR,MODEL,FSTYPE,LABEL,PARTTYPE,PTTYPE",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        data: object = json.loads(result.stdout)
    except OSError, ValueError:
        return []
    match parse_lsblk(data):
        case ParseError():
            return []
        case devices:
            return devices


def display_name(dev: Device) -> str:
    return (
        f"{(dev.vendor or '').strip()} {(dev.model or '').strip()}".strip() or dev.name
    )


def wrong_type(part: Partition) -> bool:
    """True if Mac/Windows won't open this partition because of its table type."""
    fstype, have = part.fstype, (part.parttype or "").lower()
    if fstype not in _MBR_OK or not have:
        return False
    if part.pttype == "dos":
        try:
            return int(have, 16) not in _MBR_OK[fstype]
        except ValueError:
            return False
    return part.pttype == "gpt" and have != _GPT_BASIC_DATA


# --- Operations (privileged steps run via the root-owned usb-helper, never a
#     shell; the helper re-validates the target is a removable USB disk) ---


def _helper(
    args: list[str], failed: str, stdin: IO[bytes] | None = None
) -> TaskFailed | None:
    """Run one usb-helper command through pkexec; its stderr is the failure."""
    try:
        result = subprocess.run(
            ["pkexec", HELPER, *args],
            stdin=stdin,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as e:
        return TaskFailed(str(e))
    if result.returncode == 0:
        return None
    return TaskFailed(result.stderr.strip() or failed)


def format_device(
    dev_name: str, fstype: str, label: str | None = None
) -> TaskFailed | None:
    if fstype not in FS_TYPES:
        return TaskFailed(f"Unknown filesystem: {fstype}")
    if label and not _LABEL_RE.match(label):
        return TaskFailed("Label may only contain letters, numbers, - and _")
    args = ["format", f"/dev/{dev_name}", fstype]
    if label:
        args.append(label)
    return _helper(args, "Format failed")


def mount_toggle(dev_name: str, *, mount: bool) -> TaskFailed | None:
    return _helper(
        ["mount" if mount else "unmount", f"/dev/{dev_name}"], "Mount failed"
    )


def fix_type(dev_name: str) -> TaskFailed | None:
    return _helper(["fix-type", f"/dev/{dev_name}"], "Fix failed")


def write_iso(iso_path: str, dev_name: str) -> TaskFailed | None:
    # Open the image as the unprivileged user and stream it to the helper's
    # stdin, so root never opens an arbitrary path.
    # _helper returns its own errors: an OSError here is the image's
    try:
        with Path(iso_path).open("rb") as iso:
            return _helper(["write-iso", f"/dev/{dev_name}"], "Write failed", iso)
    except OSError as e:
        return TaskFailed(f"Cannot read ISO: {e}")


def refresh_waybar() -> None:
    subprocess.Popen(
        ["pkill", "-RTMIN+12", "waybar"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# --- Widget ---


class UsbPopup(WidgetPopup):
    def __init__(self) -> None:
        super().__init__(application_id="dev.dotfiles.usb")
        self._monitor_id = 0
        self._poll_id = 0
        self._udev_proc: subprocess.Popen[bytes] | None = None
        self._busy: dict[str, str] = {}
        self._busy_meta: dict[
            str, tuple[int, int]
        ] = {}  # dev -> (total, start_sectors)
        self._busy_labels: dict[str, Gtk.Label] = {}
        self._error: str | None = None  # last failed task's message, until next rebuild

    @override
    def build_ui(self) -> Gtk.Widget:
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._container.add_css_class("usb-container")
        self._build_ui()
        self._start_monitor()
        self._start_poll()
        return self._container

    def _clear_container(self) -> None:
        while child := self._container.get_first_child():
            self._container.remove(child)

    def _on_refresh(self, _btn: Gtk.Button) -> None:
        self._build_ui()

    def _build_ui(self) -> None:
        self._clear_container()
        self._busy_labels = {}

        devices = lsblk()

        # Restore busy state from disk for devices we don't know about
        for dev in devices:
            if dev.name not in self._busy and (busy := _load_busy(dev.name)):
                self._busy[dev.name] = busy.text
                self._busy_meta[dev.name] = (busy.total, busy.start_sectors)

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="USB Devices")
        title.add_css_class("usb-title")
        title.set_hexpand(True)
        title.set_halign(Gtk.Align.START)
        title_row.append(title)

        refresh_btn = Gtk.Button(label="󰑐")
        refresh_btn.add_css_class("usb-refresh-btn")
        refresh_btn.set_tooltip_text("Refresh")
        refresh_btn.connect("clicked", self._on_refresh)
        title_row.append(refresh_btn)
        self._container.append(title_row)

        if self._error:
            err = Gtk.Label(label=self._error, xalign=0, wrap=True)
            err.add_css_class("usb-warning")
            copyable(err)
            self._container.append(err)
            self._error = None

        if not devices:
            empty = Gtk.Label(label="No USB devices detected")
            empty.add_css_class("usb-empty")
            self._container.append(empty)
            return

        for dev in devices:
            self._add_device(dev)

    def _add_device(self, dev: Device) -> None:
        busy = dev.name in self._busy

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.add_css_class("usb-device-header")

        icon = Gtk.Label(label="󰗮")
        icon.add_css_class("usb-device-icon")
        header.append(icon)
        header.append(self._device_info(dev))
        self._container.append(header)
        self._container.append(self._device_buttons(dev, busy=busy))

    def _device_info(self, dev: Device) -> Gtk.Box:
        """Name, path and size, the running task, and a line per partition."""
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)
        name_label = CopyLabel("usb-device-name")
        name_label.set_content(display_name(dev))
        info_box.append(name_label)

        size = dev.size if dev.size is not None else "?"
        detail = Gtk.Label(label=f"/dev/{dev.name}  {size}")
        detail.add_css_class("usb-device-detail")
        detail.set_halign(Gtk.Align.START)
        info_box.append(detail)

        if dev.name in self._busy:
            busy_label = Gtk.Label(label=self._busy[dev.name])
            busy_label.add_css_class("usb-device-busy")
            busy_label.set_halign(Gtk.Align.START)
            busy_label.set_ellipsize(Pango.EllipsizeMode.END)
            info_box.append(busy_label)

            progress_label = Gtk.Label(label="0%")
            progress_label.add_css_class("usb-device-progress")
            progress_label.set_halign(Gtk.Align.START)
            info_box.append(progress_label)
            self._busy_labels[dev.name] = progress_label

        for p in dev.parts:
            parts_text = "  ".join(x for x in [p.label, p.fstype, p.size] if x)
            if parts_text:
                pl = Gtk.Label(label=parts_text)
                pl.add_css_class("usb-partition-info")
                pl.set_halign(Gtk.Align.START)
                info_box.append(pl)
            if wrong_type(p):
                wl = Gtk.Label(label="Linux partition type: won't open on Mac/Windows")
                wl.add_css_class("usb-partition-warning")
                wl.set_halign(Gtk.Align.START)
                info_box.append(wl)
            if p.mountpoint:
                mp = CopyLabel("usb-mountpoint")
                mp.set_content(p.mountpoint)
                info_box.append(mp)
        return info_box

    def _device_buttons(self, dev: Device, *, busy: bool) -> Gtk.Box:
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_row.add_css_class("usb-action-row")

        mounted = any(p.mountpoint for p in dev.parts)
        mount_btn = Gtk.Button(label="Unmount" if mounted else "Mount")
        mount_btn.add_css_class("usb-action-btn")
        mount_btn.set_sensitive(
            not busy and (mounted or any(p.fstype for p in dev.parts))
        )
        mount_btn.connect(
            "clicked",
            self._on_task_clicked,
            partial(mount_toggle, dev.name, mount=not mounted),
        )
        btn_row.append(mount_btn)

        if any(wrong_type(p) for p in dev.parts):
            fix_btn = Gtk.Button(label="Fix for Mac/Win")
            fix_btn.add_css_class("usb-action-btn")
            fix_btn.set_tooltip_text("Retag the partition type only; files are kept")
            fix_btn.set_sensitive(not busy)
            fix_btn.connect(
                "clicked", self._on_task_clicked, partial(fix_type, dev.name)
            )
            btn_row.append(fix_btn)

        format_btn = Gtk.Button(label="Format")
        format_btn.add_css_class("usb-action-btn")
        format_btn.set_sensitive(not busy)
        format_btn.connect("clicked", self._on_format_clicked, dev)
        btn_row.append(format_btn)

        iso_btn = Gtk.Button(label="Write ISO")
        iso_btn.add_css_class("usb-action-btn")
        iso_btn.set_sensitive(not busy)
        iso_btn.connect("clicked", self._on_iso_clicked, dev)
        btn_row.append(iso_btn)
        return btn_row

    def _on_task_clicked(
        self, _btn: Gtk.Button, task_fn: Callable[[], TaskFailed | None]
    ) -> None:
        self._run_task(task_fn)

    def _on_format_clicked(self, _btn: Gtk.Button, dev: Device) -> None:
        self._show_format(dev)

    def _on_iso_clicked(self, _btn: Gtk.Button, dev: Device) -> None:
        self._pick_iso(dev)

    # --- Task runner ---

    def _run_task(
        self,
        task_fn: Callable[[], TaskFailed | None],
        dev_name: str | None = None,
        busy_text: str | None = None,
        total: int = 0,
    ) -> None:
        if dev_name and busy_text:
            self._busy[dev_name] = busy_text
            _save_busy(dev_name, busy_text, total)
            if total:
                self._busy_meta[dev_name] = (total, _read_sectors(dev_name))
            self._build_ui()

        def worker() -> None:
            failed = task_fn()
            GLib.idle_add(self._task_done, dev_name, str(failed) if failed else None)

        in_background(worker, partial(self._task_done, dev_name))

    def _task_done(self, dev_name: str | None, error: str | None) -> bool:
        if error:
            self._error = error
        if dev_name:
            self._busy.pop(dev_name, None)
            self._busy_meta.pop(dev_name, None)
            _clear_busy(dev_name)
        refresh_waybar()
        self._build_ui()
        return GLib.SOURCE_REMOVE

    # --- Actions ---

    def _pick_iso(self, dev: Device) -> None:
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
        dialog.open(win, None, self._on_iso_picked, dev, win)

    def _on_iso_picked(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
        dev: Device,
        win: Gtk.Window | None,
    ) -> None:
        try:
            iso_path = dialog.open_finish(result).get_path()
        except GLib.Error:
            iso_path = None
        if win:
            win.set_visible(True)
        if iso_path is None:
            return
        total = Path(iso_path).stat().st_size
        self._run_task(
            partial(write_iso, iso_path, dev.name),
            dev.name,
            f"Writing {Path(iso_path).name}...",
            total,
        )

    # --- Format ---

    def _show_format(self, dev: Device) -> None:
        self._clear_container()

        title = Gtk.Label(label=f"Format {display_name(dev)}")
        title.add_css_class("usb-title")
        self._container.append(title)

        warning = Gtk.Label(label=f"All data on /dev/{dev.name} will be erased!")
        warning.add_css_class("usb-warning")
        self._container.append(warning)

        fs_label = Gtk.Label(label="FILESYSTEM")
        fs_label.add_css_class("usb-field-label")
        fs_label.set_halign(Gtk.Align.START)
        self._container.append(fs_label)

        fs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._fs_buttons: dict[str, Gtk.ToggleButton] = {}
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
        cancel_btn.connect("clicked", self._on_refresh)
        btn_row.append(cancel_btn)

        confirm_btn = Gtk.Button(label="Format")
        confirm_btn.add_css_class("usb-danger-btn")
        confirm_btn.connect("clicked", self._on_confirm_format, dev)
        btn_row.append(confirm_btn)

        self._container.append(btn_row)

    def _on_fs_toggled(self, btn: Gtk.ToggleButton, fs: str) -> None:
        if btn.get_active():
            self._selected_fs = fs
            for name, b in self._fs_buttons.items():
                if name != fs:
                    b.set_active(False)
                    b.remove_css_class("usb-fs-active")
            btn.add_css_class("usb-fs-active")
        elif self._selected_fs == fs:
            btn.set_active(True)

    def _on_confirm_format(self, _btn: Gtk.Button, dev: Device) -> None:
        label = self._label_entry.get_text().strip() or None
        self._run_task(
            partial(format_device, dev.name, self._selected_fs, label),
            dev.name,
            "Formatting...",
        )

    # --- USB hotplug monitor ---

    def _start_monitor(self) -> None:
        try:
            self._udev_proc = subprocess.Popen(
                ["udevadm", "monitor", "--subsystem-match=block", "--udev"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return
        events = self._udev_proc.stdout
        if events is None:
            return

        def watch() -> None:
            for line in iter(events.readline, b""):
                text = line.decode(errors="replace")
                if "add" in text or "remove" in text:
                    if self._monitor_id:
                        GLib.source_remove(self._monitor_id)
                    self._monitor_id = GLib.timeout_add(500, self._on_usb_change)

        in_background(watch, partial(self._task_done, None))

    def _on_usb_change(self) -> bool:
        self._monitor_id = 0
        refresh_waybar()
        self._build_ui()
        return GLib.SOURCE_REMOVE

    def _start_poll(self) -> None:
        if not self._poll_id:
            self._poll_id = GLib.timeout_add(1000, self._poll_busy)

    def _poll_busy(self) -> bool:
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

    @override
    def do_shutdown(self) -> None:
        if self._poll_id:
            GLib.source_remove(self._poll_id)
            self._poll_id = 0
        if self._udev_proc and self._udev_proc.poll() is None:
            self._udev_proc.terminate()
        Gtk.Application.do_shutdown(self)


def main() -> int:
    return UsbPopup().run()
