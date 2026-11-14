"""Peak meter streams for the audio popup, on their own pulse connection and thread.

Same approach as pavucontrol: one PA_STREAM_PEAK_DETECT record stream per meter,
float32 mono at METER_RATE Hz with a one-sample fragment, so the server does the
peak detection and each read carries a sample or two.

libpulse's standard mainloop is not thread-safe, so every stream call runs on
the meter thread between mainloop iterations. The GTK main thread only hands over the
wanted set of streams (set_targets, latest wins) and takes the peaks collected
since its last look (take_peaks) after on_peaks wakes it via GLib.idle_add.
"""

import contextlib
import ctypes
import threading
from collections.abc import Callable, Hashable, Mapping

from gi.repository import GLib

from gtk_widgets.lib import pulsectl
from gtk_widgets.lib.pulsectl import _pulsectl as c
from gtk_widgets.lib.ui.background import in_background
from gtk_widgets.widgets.audio.parts import APP_ID

METER_RATE = 30  # peaks per second per stream
MIN_PEAK = 1e-6  # 1% of a meter on its cubic scale; silence is not sent to GTK
# Mixers' meter streams (ours included) are source outputs; like pavucontrol,
# the Recording tab hides them.
MIXER_APP_IDS = {
    APP_ID,
    "org.PulseAudio.pavucontrol",
    "org.gnome.VolumeControl",
    "org.kde.kmixd",
}

_FLAGS = c.PA_STREAM_DONT_MOVE | c.PA_STREAM_PEAK_DETECT | c.PA_STREAM_ADJUST_LATENCY
_NO_CALLBACK = c.PA_STREAM_REQUEST_CB_T()  # NULL

# (source index, sink input index to monitor or None, passive)
type MeterSpec = tuple[int, int | None, bool]


class Meters[K: Hashable]:
    """Connects, then keeps one record stream per target until stopped or disconnected.

    Uses the pulsectl connection's mainloop and context directly: pulsectl's
    own loop helpers block and have no way to run stream callbacks alongside
    commands from another thread.
    """

    def __init__(self, on_peaks: Callable[[], bool]) -> None:
        self._on_peaks = on_peaks
        self._lock = threading.Lock()
        self._loop: c.MainloopPointer | None = None  # set while it may be woken
        self._stopping = False
        self._targets: dict[K, MeterSpec] | None = None  # pending set_targets() value
        self._peaks: dict[K, float] = {}  # key -> max peak since the last take_peaks()
        # key -> (spec, stream, read callback); thread only
        self._streams: dict[
            K, tuple[MeterSpec, c.StreamPointer, c.StreamRequestCallback]
        ] = {}
        # streams closed while still being created; thread only
        self._closing: list[c.StreamPointer] = []

    # --- main thread ---

    def start(self, on_bug: Callable[[str], bool | None]) -> None:
        in_background(self._run, on_bug)

    def set_targets(self, targets: Mapping[K, MeterSpec]) -> None:
        """A passive stream (pavucontrol: monitors) does not wake a suspended
        device; an active one (microphones) does, so the meter shows input.
        """
        with self._lock:
            self._targets = dict(targets)
            self._wake()

    def take_peaks(self) -> dict[K, float]:
        with self._lock:
            peaks, self._peaks = self._peaks, {}
        return peaks

    def stop(self) -> None:
        """Thread-safe; the thread disconnects every stream and closes the connection."""
        with self._lock:
            self._stopping = True
            self._wake()

    def _wake(self) -> None:
        if self._loop is not None:
            c.pa.mainloop_wakeup(self._loop)

    # --- meter thread ---

    def _run(self) -> None:
        try:
            pulse = pulsectl.Pulse("gtk-widgets-audio-meters")
        except pulsectl.PulseError:
            return  # the event connection notices a dead server and reconnects
        proplist = c.pa.proplist_from_string(f"application.id={APP_ID}")
        with self._lock:
            self._loop = pulse.mainloop
        try:
            with contextlib.suppress(c.pa.CallError):  # mainloop error: connection gone
                self._serve(pulse, proplist)
        finally:
            with self._lock:
                self._loop = None
            for key in list(self._streams):
                self._close(key)
            for stream in self._closing:
                c.pa.stream_unref(stream)  # closing the connection ends them
            c.pa.proplist_free(proplist)
            pulse.close()

    def _serve(self, pulse: pulsectl.Pulse, proplist: c.ProplistPointer) -> None:
        while True:
            with self._lock:
                if self._stopping:
                    return
                targets, self._targets = self._targets, None
            if targets is not None:
                self._apply(pulse, proplist, targets)
            # mainloop_wakeup() from set_targets()/stop() ends a blocking iterate
            c.pa.mainloop_iterate(pulse.mainloop, 1, None)
            if not pulse.connected:
                return
            if self._closing:
                self._reap()

    def _apply(
        self,
        pulse: pulsectl.Pulse,
        proplist: c.ProplistPointer,
        targets: dict[K, MeterSpec],
    ) -> None:
        for key in [
            k for k, (spec, _, _) in self._streams.items() if targets.get(k) != spec
        ]:
            self._close(key)
        for key, spec in targets.items():
            if key not in self._streams:
                self._open(pulse, proplist, key, spec)

    def _open(
        self,
        pulse: pulsectl.Pulse,
        proplist: c.ProplistPointer,
        key: K,
        spec: MeterSpec,
    ) -> None:
        source, monitor, passive = spec
        ss = c.PA_SAMPLE_SPEC(format=c.PA_SAMPLE_FLOAT32NE, rate=METER_RATE, channels=1)
        stream = c.pa.stream_new_with_proplist(
            pulse.context, "Peak detect", ctypes.byref(ss), None, proplist
        )
        if not stream:
            return
        callback = c.PA_STREAM_REQUEST_CB_T(lambda s, _n, _u: self._on_read(s, key))
        attr = c.PA_BUFFER_ATTR(
            maxlength=2**32 - 1, fragsize=ctypes.sizeof(ctypes.c_float)
        )
        try:
            if monitor is not None:
                c.pa.stream_set_monitor_stream(stream, monitor)
            c.pa.stream_set_read_callback(stream, callback, None)
            flags = _FLAGS | (c.PA_STREAM_DONT_INHIBIT_AUTO_SUSPEND if passive else 0)
            c.pa.stream_connect_record(stream, str(source), ctypes.byref(attr), flags)
        except c.pa.CallError:
            c.pa.stream_unref(stream)
            return  # retried when the targets next change
        self._streams[key] = (spec, stream, callback)

    def _close(self, key: K) -> None:
        _, stream, _ = self._streams.pop(key)
        c.pa.stream_set_read_callback(stream, _NO_CALLBACK, None)
        with self._lock:
            self._peaks.pop(key, None)
        if c.pa.stream_get_state(stream) == c.PA_STREAM_CREATING:
            # disconnect() fails until the server has created it, which would leak it
            self._closing.append(stream)
        else:
            self._release(stream)

    def _reap(self) -> None:
        for stream in [
            s for s in self._closing if c.pa.stream_get_state(s) != c.PA_STREAM_CREATING
        ]:
            self._closing.remove(stream)
            self._release(stream)

    @staticmethod
    def _release(stream: c.StreamPointer) -> None:
        if c.pa.stream_get_state(stream) == c.PA_STREAM_READY:
            with contextlib.suppress(c.pa.CallError):
                c.pa.stream_disconnect(stream)
        c.pa.stream_unref(
            stream
        )  # a failed one (device or monitored stream gone) is gone

    def _on_read(self, stream: c.StreamPointer, key: K) -> None:
        data, nbytes = ctypes.c_void_p(), ctypes.c_size_t()
        try:
            c.pa.stream_peek(stream, ctypes.byref(data), ctypes.byref(nbytes))
        except c.pa.CallError:
            return
        if not nbytes.value:
            return  # empty buffer: nothing to drop
        peak = 0.0
        if data.value:  # NULL data with a length is a hole: drop it, no samples
            count = nbytes.value // ctypes.sizeof(ctypes.c_float)
            samples = (ctypes.c_float * count).from_address(data.value)
            peak = max((abs(s) for s in samples), default=0.0)
        c.pa.stream_drop(stream)
        if peak < MIN_PEAK:
            return  # GTK decays meters on its own
        with self._lock:
            notify = not self._peaks
            if peak > self._peaks.get(key, 0.0):
                self._peaks[key] = peak
        if notify:
            GLib.idle_add(self._on_peaks)
