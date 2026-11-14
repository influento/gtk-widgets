"""lsblk's device list and the busy-state file: their models and parsers."""

from dataclasses import dataclass

from gtk_widgets.lib.parse import (
    ParseError,
    as_array,
    as_bool,
    as_int,
    as_str,
    as_str_or_none,
    is_object,
)


@dataclass(frozen=True, slots=True)
class Partition:
    fstype: str | None
    label: str | None
    size: str | None
    mountpoint: str | None
    parttype: str | None  # MBR type as hex, or a GPT type GUID
    pttype: str | None  # partition table: "dos" or "gpt"


@dataclass(frozen=True, slots=True)
class Device:
    """A removable USB disk."""

    name: str  # sdb: /dev/sdb
    size: str | None
    vendor: str | None
    model: str | None
    parts: list[Partition]


@dataclass(frozen=True, slots=True)
class Busy:
    """A task running on a device, as saved for the next popup."""

    text: str
    total: int  # bytes an ISO write puts on the device, 0 for other tasks
    start_sectors: int  # the device's sectors written when the task began


def _partition(value: object, path: str) -> Partition | ParseError | None:
    """A child of type "part"; None for other children."""
    if not is_object(value):
        return ParseError(f"{path}: not an object")
    kind = as_str_or_none(value.get("type"), f"{path}.type")
    if kind != "part":
        return kind if isinstance(kind, ParseError) else None
    match tuple(
        as_str_or_none(value.get(key), f"{path}.{key}")
        for key in ("fstype", "label", "size", "mountpoint", "parttype", "pttype")
    ):
        case (
            (str() | None) as fstype,
            (str() | None) as label,
            (str() | None) as size,
            (str() | None) as mountpoint,
            (str() | None) as parttype,
            (str() | None) as pttype,
        ):
            return Partition(fstype, label, size, mountpoint, parttype, pttype)
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))


def _device(value: object, path: str) -> Device | ParseError | None:
    """A disk on the USB bus marked removable; None for other devices."""
    if not is_object(value):
        return ParseError(f"{path}: not an object")
    match (
        as_str_or_none(value.get("tran"), f"{path}.tran"),
        as_bool(value.get("rm", False), f"{path}.rm"),
    ):
        case "usb", True:
            pass
        case ((str() | None), bool()):
            return None
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))
    children = as_array(value.get("children"), f"{path}.children")
    if isinstance(children, ParseError):
        return children
    parts: list[Partition] = []
    for i, child in enumerate(children):
        match _partition(child, f"{path}.children[{i}]"):
            case ParseError() as e:
                return e
            case None:
                pass
            case part:
                parts.append(part)
    match (
        as_str(value.get("name"), f"{path}.name"),
        as_str_or_none(value.get("size"), f"{path}.size"),
        as_str_or_none(value.get("vendor"), f"{path}.vendor"),
        as_str_or_none(value.get("model"), f"{path}.model"),
    ):
        case (
            str() as name,
            (str() | None) as size,
            (str() | None) as vendor,
            (str() | None) as model,
        ):
            return Device(name, size, vendor, model, parts)
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))


def parse_lsblk(data: object) -> list[Device] | ParseError:
    """`lsblk -J -o NAME,SIZE,TYPE,...`: its removable USB disks."""
    if not is_object(data):
        return ParseError("not an object")
    devices = as_array(data.get("blockdevices"), ".blockdevices")
    if isinstance(devices, ParseError):
        return devices
    found: list[Device] = []
    for i, value in enumerate(devices):
        match _device(value, f".blockdevices[{i}]"):
            case ParseError() as e:
                return e
            case None:
                pass
            case device:
                found.append(device)
    return found


def parse_busy(data: object) -> Busy | ParseError:
    if not is_object(data):
        return ParseError("not an object")
    match (
        as_str(data.get("text"), ".text"),
        as_int(data.get("total", 0), ".total"),
        as_int(data.get("start_sectors", 0), ".start_sectors"),
    ):
        case str() as text, int() as total, int() as start:
            return Busy(text, total, start)
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))
