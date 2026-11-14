"""Grab every output's raw framebuffer with wlr-screencopy (stdlib only).

A minimal Wayland client speaking the wire protocol straight over the
compositor socket: no libwayland, no GTK, so the shot is taken a few ms after
launch, before any window of ours maps or takes focus. Each frame comes back
at the output's physical resolution, exactly as the compositor rendered it:
no compositing of outputs, no scaling. The cursor is left out. The wire
protocol itself is lib/wayland.py.
"""

import mmap
import os
import struct
import time

from gtk_widgets.lib.wayland import Connection, Handler, Reader, WaylandError

# wl_output.transform: 0 normal, 1-3 rotated 90/180/270 counter-clockwise,
# 4-7 the same after a flip around the vertical axis
TRANSFORM_NORMAL = 0

# wl_shm formats (DRM fourcc, except the two legacy codes 0 and 1) that
# GdkMemoryFormat reads as is: value -> (name, byte order in memory)
SHM_FORMATS = {
    0: ("ARGB8888", "BGRA"),
    1: ("XRGB8888", "BGRX"),
    0x34324241: ("ABGR8888", "RGBA"),
    0x34324258: ("XBGR8888", "RGBX"),
}

Y_INVERT = 1  # zwlr_screencopy_frame_v1.flags
MODE_CURRENT = 1  # wl_output.mode flags

# Event opcodes
_OUTPUT_GEOMETRY, _OUTPUT_MODE, _OUTPUT_SCALE, _OUTPUT_NAME = 0, 1, 3, 4
_FRAME_BUFFER, _FRAME_FLAGS, _FRAME_READY, _FRAME_FAILED = 0, 1, 2, 3
_FRAME_BUFFER_DONE = 6
_MANAGER_MAX_VERSION = 3  # buffer_done and the list of every buffer type
_OUTPUT_MAX_VERSION = 4  # the name event

type ShmOffer = tuple[int, int, int, int]  # format, width, height, stride

CaptureError = WaylandError  # what main.py catches


class Output:
    def __init__(self, global_name: int) -> None:
        self.global_name = global_name
        self.id = 0  # the bound wl_output
        self.name = ""  # connector, e.g. HDMI-A-1 (wl_output v4)
        self.transform = TRANSFORM_NORMAL
        self.scale = 1  # integer wl_output.scale; the fractional one comes from GDK
        self.x = self.y = 0
        self.mode: tuple[int, int] = (0, 0)


class Frame:
    """One output's pixels in buffer orientation (wl_output transform and
    y_invert not applied yet): data rows of stride bytes, format a key of
    SHM_FORMATS."""

    def __init__(
        self,
        output: Output,
        data: bytes,
        size: tuple[int, int],
        stride: int,
        fmt: int,
        *,
        y_invert: bool,
    ) -> None:
        self.output = output
        self.data = data
        self.width, self.height = size
        self.stride = stride
        self.format = fmt
        self.y_invert = y_invert


def _ignore(_opcode: int, _r: Reader) -> None:
    pass


def _output_handler(out: Output) -> Handler:
    def handle(opcode: int, r: Reader) -> None:
        if opcode == _OUTPUT_GEOMETRY:
            # x, y, mm width, mm height, subpixel, make, model, transform
            out.x, out.y = r.int(), r.int()
            _ = r.int(), r.int(), r.int(), r.string(), r.string()
            out.transform = r.int()
        elif opcode == _OUTPUT_MODE:  # flags, width, height, refresh
            flags, w, h = r.uint(), r.int(), r.int()
            if flags & MODE_CURRENT:
                out.mode = (w, h)
        elif opcode == _OUTPUT_SCALE:
            out.scale = r.int()
        elif opcode == _OUTPUT_NAME:
            out.name = r.string()

    return handle


class _FrameState:
    def __init__(self, output: Output) -> None:
        self.output = output
        self.id = 0  # the zwlr_screencopy_frame_v1
        self.offset = 0  # of its buffer in the pool
        self.shm: ShmOffer | None = None  # the first usable shm offer
        self.offers: list[ShmOffer] = []
        self.buffer_done = False
        self.flags = 0
        self.ready = False
        self.failed = False

    def handle(self, opcode: int, r: Reader) -> None:
        if opcode == _FRAME_BUFFER:  # format, width, height, stride
            offer = (r.uint(), r.uint(), r.uint(), r.uint())
            self.offers.append(offer)
            if self.shm is None and offer[0] in SHM_FORMATS:
                self.shm = offer
        elif opcode == _FRAME_FLAGS:
            self.flags = r.uint()
        elif opcode == _FRAME_READY:
            self.ready = True
        elif opcode == _FRAME_FAILED:
            self.failed = True
        elif opcode == _FRAME_BUFFER_DONE:
            self.buffer_done = True


def capture_outputs() -> list[Frame]:
    """Grab every output. Returns [Frame], in the compositor's output order."""
    conn = Connection()
    try:
        return _capture(conn)
    finally:
        conn.close()


def _bind(conn: Connection) -> tuple[int, int, int, list[Output]]:
    """(wl_shm, the screencopy manager, its version, the outputs), bound."""
    shm = manager = 0
    manager_version = 0
    outputs: list[Output] = []
    for name, interface, version in conn.globals():
        if interface == "wl_shm":
            shm = conn.bind(name, interface, 1, _ignore)
        elif interface == "zwlr_screencopy_manager_v1":
            manager_version = min(version, _MANAGER_MAX_VERSION)
            manager = conn.bind(name, interface, manager_version, _ignore)
        elif interface == "wl_output":
            out = Output(name)
            out.id = conn.bind(
                name, interface, min(version, _OUTPUT_MAX_VERSION), _output_handler(out)
            )
            outputs.append(out)
    if not manager:
        raise CaptureError(
            "the compositor has no wlr-screencopy (zwlr_screencopy_manager_v1)"
        )
    if not shm or not outputs:
        raise CaptureError("the compositor offers no wl_shm or no outputs")
    return shm, manager, manager_version, outputs


def _offers(
    conn: Connection, manager: int, manager_version: int, outputs: list[Output]
) -> list[tuple[_FrameState, ShmOffer]]:
    """Ask for a frame of each output; each with the shm buffer it takes."""
    states: list[_FrameState] = []
    for out in outputs:
        st = _FrameState(out)
        st.id = conn.new_id(st.handle)
        # capture_output(frame, overlay_cursor=0, output)
        conn.send(manager, 0, struct.pack("=IiI", st.id, 0, out.id))
        states.append(st)
    # v3 lists every buffer type and ends with buffer_done; before v3 the
    # single buffer event is all there is
    while not all(
        st.buffer_done
        or (manager_version < _MANAGER_MAX_VERSION and st.offers)
        or st.failed
        for st in states
    ):
        conn.dispatch()
    found: list[tuple[_FrameState, ShmOffer]] = []
    for st in states:
        if st.failed:
            raise CaptureError(
                f"the compositor refused to capture {st.output.name or 'an output'}"
            )
        if st.shm is None:
            offered = ", ".join(f"0x{o[0]:08x}" for o in st.offers) or "none"
            raise CaptureError(
                f"{st.output.name}: no supported shm format (offered {offered})"
            )
        found.append((st, st.shm))
    return found


def _capture(conn: Connection) -> list[Frame]:
    shm, manager, manager_version, outputs = _bind(conn)
    conn.roundtrip()  # output geometry, mode, name
    states = _offers(conn, manager, manager_version, outputs)

    sizes = [offer[2] * offer[3] for _, offer in states]
    fd = os.memfd_create("capture", os.MFD_CLOEXEC)
    try:
        os.ftruncate(fd, sum(sizes))
        pool = conn.new_id(_ignore)
        conn.send(shm, 0, struct.pack("=Ii", pool, sum(sizes)), fds=[fd])  # create_pool
        offset = 0
        for (st, (fmt, w, h, stride)), size in zip(states, sizes, strict=True):
            buf = conn.new_id(_ignore)
            conn.send(pool, 0, struct.pack("=IiiiiI", buf, offset, w, h, stride, fmt))
            conn.send(st.id, 0, struct.pack("=I", buf))  # copy
            st.offset = offset
            offset += size
        conn.send(pool, 1)  # destroy: the buffers keep the memory
        while not all(st.ready or st.failed for st, _ in states):
            conn.dispatch()
        with mmap.mmap(fd, sum(sizes), mmap.MAP_SHARED, mmap.PROT_READ) as mem:
            frames: list[Frame] = []
            for (st, (fmt, w, h, stride)), size in zip(states, sizes, strict=True):
                if st.failed:
                    raise CaptureError(
                        f"capturing {st.output.name or 'an output'} failed"
                    )
                frames.append(
                    Frame(
                        st.output,
                        mem[st.offset : st.offset + size],
                        (w, h),
                        stride,
                        fmt,
                        y_invert=bool(st.flags & Y_INVERT),
                    )
                )
    finally:
        os.close(fd)
    return frames


if __name__ == "__main__":
    t = time.perf_counter()
    for f in capture_outputs():
        o = f.output
        print(
            o.name,
            f"{f.width}x{f.height}",
            "stride",
            f.stride,
            SHM_FORMATS[f.format][0],
            "transform",
            o.transform,
            "y_invert",
            f.y_invert,
            "at",
            (o.x, o.y),
            "scale",
            o.scale,
        )
    print(f"{(time.perf_counter() - t) * 1000:.1f} ms")
