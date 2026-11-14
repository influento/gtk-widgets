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

from gtk_widgets.lib.wayland import Connection, WaylandError

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


CaptureError = WaylandError  # what main.py catches


class Frame:
    """One output's pixels in buffer orientation (wl_output transform and
    y_invert not applied yet): data rows of stride bytes, format a key of
    SHM_FORMATS."""

    def __init__(self, output, data, width, height, stride, fmt, y_invert):
        self.output = output
        self.data = data
        self.width = width
        self.height = height
        self.stride = stride
        self.format = fmt
        self.y_invert = y_invert


class Output:
    def __init__(self, global_name):
        self.global_name = global_name
        self.name = ""  # connector, e.g. HDMI-A-1 (wl_output v4)
        self.transform = TRANSFORM_NORMAL
        self.scale = 1  # integer wl_output.scale; the fractional one comes from GDK
        self.x = self.y = 0
        self.mode = (0, 0)


def _output_handler(out):
    def handle(opcode, r):
        if opcode == 0:  # geometry(x, y, mm w, mm h, subpixel, make, model, transform)
            out.x, out.y = r.int(), r.int()
            r.int(), r.int(), r.int(), r.string(), r.string()
            out.transform = r.int()
        elif opcode == 1:  # mode(flags, width, height, refresh)
            flags, w, h = r.uint(), r.int(), r.int()
            if flags & 1:  # current
                out.mode = (w, h)
        elif opcode == 3:  # scale
            out.scale = r.int()
        elif opcode == 4:  # name
            out.name = r.string()

    return handle


class _FrameState:
    def __init__(self, output):
        self.output = output
        self.shm = None  # (format, width, height, stride) of the first usable shm offer
        self.offers = []
        self.buffer_done = False
        self.flags = 0
        self.ready = False
        self.failed = False

    def handle(self, opcode, r):
        if opcode == 0:  # buffer(format, width, height, stride)
            offer = (r.uint(), r.uint(), r.uint(), r.uint())
            self.offers.append(offer)
            if self.shm is None and offer[0] in SHM_FORMATS:
                self.shm = offer
        elif opcode == 1:
            self.flags = r.uint()
        elif opcode == 2:
            self.ready = True
        elif opcode == 3:
            self.failed = True
        elif opcode == 6:
            self.buffer_done = True


def capture_outputs():
    """Grab every output. Returns [Frame], in the compositor's output order."""
    conn = Connection()
    try:
        return _capture(conn)
    finally:
        conn.close()


def _capture(conn):
    globals_ = conn.globals()
    shm = manager = None
    manager_version = 0
    outputs = []
    for name, interface, version in globals_:
        if interface == "wl_shm":
            shm = conn.bind(name, interface, 1, lambda op, r: None)
        elif interface == "zwlr_screencopy_manager_v1":
            manager_version = min(version, 3)
            manager = conn.bind(name, interface, manager_version, lambda op, r: None)
        elif interface == "wl_output":
            out = Output(name)
            out.id = conn.bind(name, interface, min(version, 4), _output_handler(out))
            outputs.append(out)
    if manager is None:
        raise CaptureError(
            "the compositor has no wlr-screencopy (zwlr_screencopy_manager_v1)"
        )
    if shm is None or not outputs:
        raise CaptureError("the compositor offers no wl_shm or no outputs")
    conn.roundtrip()  # output geometry, mode, name

    states = []
    for out in outputs:
        st = _FrameState(out)
        st.id = conn.new_id(st.handle)
        # capture_output(frame, overlay_cursor=0, output)
        conn.send(manager, 0, struct.pack("=IiI", st.id, 0, out.id))
        states.append(st)
    # v3 lists every buffer type and ends with buffer_done; before v3 the
    # single buffer event is all there is
    while not all(
        st.buffer_done or (manager_version < 3 and st.offers) or st.failed
        for st in states
    ):
        conn.dispatch()
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

    sizes = [st.shm[2] * st.shm[3] for st in states]
    fd = os.memfd_create("capture", os.MFD_CLOEXEC)
    try:
        os.ftruncate(fd, sum(sizes))
        pool = conn.new_id(lambda op, r: None)
        conn.send(shm, 0, struct.pack("=Ii", pool, sum(sizes)), fds=[fd])  # create_pool
        offset = 0
        for st, size in zip(states, sizes):
            fmt, w, h, stride = st.shm
            buf = conn.new_id(lambda op, r: None)
            conn.send(pool, 0, struct.pack("=IiiiiI", buf, offset, w, h, stride, fmt))
            conn.send(st.id, 0, struct.pack("=I", buf))  # copy
            st.offset = offset
            offset += size
        conn.send(pool, 1)  # destroy: the buffers keep the memory
        while not all(st.ready or st.failed for st in states):
            conn.dispatch()
        with mmap.mmap(fd, sum(sizes), mmap.MAP_SHARED, mmap.PROT_READ) as mem:
            frames = []
            for st, size in zip(states, sizes):
                if st.failed:
                    raise CaptureError(
                        f"capturing {st.output.name or 'an output'} failed"
                    )
                fmt, w, h, stride = st.shm
                frames.append(
                    Frame(
                        st.output,
                        mem[st.offset : st.offset + size],
                        w,
                        h,
                        stride,
                        fmt,
                        bool(st.flags & Y_INVERT),
                    )
                )
    finally:
        os.close(fd)
    return frames


if __name__ == "__main__":
    import time

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
