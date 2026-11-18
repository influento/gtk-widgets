"""V4L2 camera controls over ioctl (stdlib): list, read, write, and the LED of
Logitech cameras through their UVC extension unit. Opening a device does not
start streaming, so controls change while another app uses the camera."""

import ctypes
import fcntl
import os
import re
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path


class CameraError(OSError):
    """A device is missing or refused a request."""


def _iowr(group: str, nr: int, size: int) -> int:
    return (3 << 30) | (size << 16) | (ord(group) << 8) | nr


def _ior(group: str, nr: int, size: int) -> int:
    return (2 << 30) | (size << 16) | (ord(group) << 8) | nr


class _Capability(ctypes.Structure):
    _fields_ = (
        ("driver", ctypes.c_char * 16),
        ("card", ctypes.c_char * 32),
        ("bus_info", ctypes.c_char * 32),
        ("version", ctypes.c_uint32),
        ("capabilities", ctypes.c_uint32),
        ("device_caps", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 3),
    )


class _QueryCtrl(ctypes.Structure):
    _fields_ = (
        ("id", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("name", ctypes.c_char * 32),
        ("minimum", ctypes.c_int32),
        ("maximum", ctypes.c_int32),
        ("step", ctypes.c_int32),
        ("default_value", ctypes.c_int32),
        ("flags", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 2),
    )


class _QueryMenu(ctypes.Structure):
    _fields_ = (
        ("id", ctypes.c_uint32),
        ("index", ctypes.c_uint32),
        ("name", ctypes.c_char * 32),
        ("reserved", ctypes.c_uint32),
    )


class _Control(ctypes.Structure):
    _fields_ = (("id", ctypes.c_uint32), ("value", ctypes.c_int32))


class _XuQuery(ctypes.Structure):
    _fields_ = (
        ("unit", ctypes.c_uint8),
        ("selector", ctypes.c_uint8),
        ("query", ctypes.c_uint8),
        ("size", ctypes.c_uint16),
        ("data", ctypes.POINTER(ctypes.c_uint8)),
    )


VIDIOC_QUERYCAP = _ior("V", 0, ctypes.sizeof(_Capability))
VIDIOC_G_CTRL = _iowr("V", 27, ctypes.sizeof(_Control))
VIDIOC_S_CTRL = _iowr("V", 28, ctypes.sizeof(_Control))
VIDIOC_QUERYCTRL = _iowr("V", 36, ctypes.sizeof(_QueryCtrl))
VIDIOC_QUERYMENU = _iowr("V", 37, ctypes.sizeof(_QueryMenu))
UVCIOC_CTRL_QUERY = _iowr("u", 0x21, ctypes.sizeof(_XuQuery))

CAP_VIDEO_CAPTURE = 0x1
CTRL_FLAG_NEXT_CTRL = 0x80000000
CTRL_FLAG_DISABLED = 0x1
CTRL_FLAG_READ_ONLY = 0x4
CTRL_FLAG_INACTIVE = 0x10
LOOPBACK_DRIVER = "v4l2 loopback"


class Kind(IntEnum):
    """The control types the popup shows (V4L2_CTRL_TYPE_*)."""

    INTEGER = 1
    BOOLEAN = 2
    MENU = 3


@dataclass(frozen=True, slots=True)
class Control:
    id: int
    key: str  # v4l2-ctl's name: "white_balance_temperature"
    label: str  # the driver's: "White Balance Temperature"
    kind: Kind
    minimum: int
    maximum: int
    step: int
    default: int
    value: int
    inactive: bool  # another control (an automatic mode) sets it now
    menu: tuple[tuple[int, str], ...]  # (value, label) of a MENU


def control_key(label: str) -> str:
    """v4l2-ctl's name for a control: lower case, runs of other characters as _."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


@contextmanager
def opened(device: Path) -> Generator[int]:
    try:
        fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
    except OSError as e:
        raise CameraError(e.errno, f"{device}: {e.strerror}") from e
    try:
        yield fd
    finally:
        os.close(fd)


def _ioctl(fd: int, request: int, arg: ctypes.Structure) -> None:
    try:
        _ = fcntl.ioctl(fd, request, arg)
    except OSError as e:
        raise CameraError(e.errno, e.strerror) from e


def _capability(device: Path) -> _Capability | None:
    cap = _Capability()
    try:
        with opened(device) as fd:
            _ioctl(fd, VIDIOC_QUERYCAP, cap)
    except CameraError:
        return None
    return cap


def card_name(device: Path) -> str:
    cap = _capability(device)
    return cap.card.decode(errors="replace") if cap else device.name


def find_camera() -> Path | None:
    """The first real camera: a capture node that is not a v4l2loopback device.
    by-id names survive replugs and other cameras coming and going."""
    by_id = Path("/dev/v4l/by-id")
    links = sorted(by_id.glob("*-video-index0")) if by_id.is_dir() else []
    for link in links or sorted(Path("/dev").glob("video*")):
        cap = _capability(link)
        if (
            cap is not None
            and cap.device_caps & CAP_VIDEO_CAPTURE
            and cap.driver.decode() != LOOPBACK_DRIVER
        ):
            return link
    return None


def find_loopback() -> Path | None:
    """The v4l2loopback device the effects engine writes to."""
    for node in sorted(Path("/dev").glob("video*")):
        cap = _capability(node)
        if cap is not None and cap.driver.decode() == LOOPBACK_DRIVER:
            return node
    return None


def _menu(fd: int, query: _QueryCtrl) -> tuple[tuple[int, str], ...]:
    items: list[tuple[int, str]] = []
    for index in range(query.minimum, query.maximum + 1):
        item = _QueryMenu(id=query.id, index=index)
        try:
            _ioctl(fd, VIDIOC_QUERYMENU, item)
        except CameraError:
            continue  # a gap: UVC menus skip values (auto_exposure has 1 and 3)
        items.append((index, item.name.decode(errors="replace")))
    return tuple(items)


def list_controls(device: Path) -> list[Control] | CameraError:
    """Every integer, boolean and menu control the device can change, in the
    driver's order (an automatic mode before the value it sets)."""
    try:
        return _list_controls(device)
    except CameraError as e:
        return e


def _list_controls(device: Path) -> list[Control]:
    found: list[Control] = []
    with opened(device) as fd:
        query = _QueryCtrl(id=CTRL_FLAG_NEXT_CTRL)
        while True:
            try:
                _ioctl(fd, VIDIOC_QUERYCTRL, query)
            except CameraError:
                break  # EINVAL: past the last control
            if query.type in {k.value for k in Kind} and not query.flags & (
                CTRL_FLAG_DISABLED | CTRL_FLAG_READ_ONLY
            ):
                current = _Control(id=query.id)
                _ioctl(fd, VIDIOC_G_CTRL, current)
                label = query.name.decode(errors="replace")
                kind = Kind(query.type)
                found.append(
                    Control(
                        id=query.id,
                        key=control_key(label),
                        label=label,
                        kind=kind,
                        minimum=query.minimum,
                        maximum=query.maximum,
                        step=max(query.step, 1),
                        default=query.default_value,
                        value=current.value,
                        inactive=bool(query.flags & CTRL_FLAG_INACTIVE),
                        menu=_menu(fd, query) if kind is Kind.MENU else (),
                    )
                )
            query = _QueryCtrl(id=query.id | CTRL_FLAG_NEXT_CTRL)
    return found


def set_control(device: Path, control_id: int, value: int) -> CameraError | None:
    try:
        with opened(device) as fd:
            _ioctl(fd, VIDIOC_S_CTRL, _Control(id=control_id, value=value))
    except CameraError as e:
        return e
    return None


def apply_values(device: Path, values: dict[str, int]) -> list[str] | CameraError:
    """Write saved values by key. Modes (booleans, menus) go first: a value an
    automatic mode sets is refused until the mode is off. Returns the keys the
    device has not or refused."""
    match list_controls(device):
        case CameraError() as e:
            return e
        case listed:
            controls = {c.key: c for c in listed}
    modes = [
        k for k in values if k in controls and controls[k].kind is not Kind.INTEGER
    ]
    rest = [k for k in values if k in controls and k not in modes]
    failed = [k for k in values if k not in controls]
    failed.extend(
        key
        for key in modes
        if set_control(device, controls[key].id, values[key]) is not None
    )
    # a value its automatic mode now sets is the mode's, not ours
    match list_controls(device):
        case CameraError() as e:
            return e
        case listed:
            inactive = {c.key for c in listed if c.inactive}
    failed.extend(
        key
        for key in rest
        if key not in inactive
        and set_control(device, controls[key].id, values[key]) is not None
    )
    return failed


# Logitech's peripheral extension unit: LED 1 is selector 9, five bytes, the
# mode in byte 1 (checked on a C920 PRO HD, 046d:08e5)
LOGITECH_PERIPHERAL_GUID = bytes.fromhex("212de5ff30802c4e82d9f587d00540bd")
LED_SELECTOR = 9
LED_SIZE = 5
LED_MODE_BYTE = 1
UVC_SET_CUR = 0x01
UVC_GET_CUR = 0x81
CS_INTERFACE = 0x24
VC_EXTENSION_UNIT = 0x06


class LedMode(IntEnum):
    OFF = 0
    ON = 1
    BLINK = 2
    AUTO = 3  # on while streaming


def _led_unit(device: Path) -> int | None:
    """The unit id of Logitech's peripheral extension unit, from the USB
    descriptors (sysfs keeps them raw beside the device)."""
    node = device.resolve().name
    raw = Path(f"/sys/class/video4linux/{node}/device/../descriptors")
    try:
        data = raw.read_bytes()
    except OSError:
        return None
    at = 0
    while at + 2 <= len(data):
        length = data[at]
        if length < 2:
            return None
        if (
            data[at + 1] == CS_INTERFACE
            and length >= 20
            and data[at + 2] == VC_EXTENSION_UNIT
            and data[at + 4 : at + 20] == LOGITECH_PERIPHERAL_GUID
        ):
            return data[at + 3]
        at += length
    return None


def _xu(fd: int, unit: int, query: int, data: bytearray) -> None:
    buf = (ctypes.c_uint8 * len(data)).from_buffer(data)
    _ioctl(
        fd,
        UVCIOC_CTRL_QUERY,
        _XuQuery(
            unit,
            LED_SELECTOR,
            query,
            len(data),
            ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint8)),
        ),
    )


def get_led(device: Path) -> LedMode | None:
    """The LED's mode; None on a camera without Logitech's LED control."""
    unit = _led_unit(device)
    if unit is None:
        return None
    data = bytearray(LED_SIZE)
    try:
        with opened(device) as fd:
            _xu(fd, unit, UVC_GET_CUR, data)
    except CameraError:
        return None
    mode = data[LED_MODE_BYTE]
    return LedMode(mode) if mode in {m.value for m in LedMode} else None


def set_led(device: Path, mode: LedMode) -> CameraError | None:
    unit = _led_unit(device)
    if unit is None:
        return CameraError(0, "this camera has no LED control")
    data = bytearray(LED_SIZE)
    try:
        with opened(device) as fd:
            _xu(fd, unit, UVC_GET_CUR, data)
            data[LED_MODE_BYTE] = mode
            _xu(fd, unit, UVC_SET_CUR, data)
    except CameraError as e:
        return e
    return None
