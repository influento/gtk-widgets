"""Peak meter streams for the audio popup, on their own pulse connection and thread.

Same approach as pavucontrol: one PA_STREAM_PEAK_DETECT record stream per meter,
float32 mono at METER_RATE Hz with a one-sample fragment, so the server does the
peak detection and each read carries a sample or two.

libpulse's standard mainloop is not thread-safe, so every stream call runs on
MeterThread between mainloop iterations. The GTK main thread only hands over the
wanted set of streams (set_targets, latest wins) and takes the peaks collected
since its last look (take_peaks) after on_peaks wakes it via GLib.idle_add.
"""

import ctypes, threading

from gi.repository import GLib

import lib.pulsectl as pulsectl
from lib.pulsectl import _pulsectl as c

METER_RATE = 30        # peaks per second per stream
MIN_PEAK = 1e-3        # -60 dBFS, the bottom of the meter scale; silence is not sent to GTK
APP_ID = "dev.dotfiles.audio"
# Mixers' meter streams (ours included) are source outputs; like pavucontrol,
# the Recording tab hides them.
MIXER_APP_IDS = {APP_ID, "org.PulseAudio.pavucontrol", "org.gnome.VolumeControl",
                 "org.kde.kmixd"}

_FLAGS = c.PA_STREAM_DONT_MOVE | c.PA_STREAM_PEAK_DETECT | c.PA_STREAM_ADJUST_LATENCY
_NO_CALLBACK = c.PA_STREAM_REQUEST_CB_T()  # NULL


class MeterThread(threading.Thread):
    """Connects, then keeps one record stream per target until stopped or disconnected.

    Uses the pulsectl connection's mainloop and context directly (Pulse._loop,
    Pulse._ctx): pulsectl's own loop helpers block and have no way to run
    stream callbacks alongside commands from another thread.
    """

    def __init__(self, on_peaks):
        super().__init__(daemon=True)
        self._on_peaks = on_peaks
        self._lock = threading.Lock()
        self._loop = None          # set while the mainloop may be woken
        self._stopping = False
        self._targets = None       # pending set_targets() value
        self._peaks = {}           # key -> max peak since the last take_peaks()
        self._streams = {}         # key -> (spec, stream, read callback); thread only
        self._closing = []         # streams closed while still being created; thread only
        self._proplist = None

    # --- main thread ---

    def set_targets(self, targets):
        """targets: {key: (source index, sink input index to monitor or None, passive)}.

        A passive stream (pavucontrol: monitors) does not wake a suspended
        device; an active one (microphones) does, so the meter shows input.
        """
        with self._lock:
            self._targets = dict(targets)
            self._wake()

    def take_peaks(self):
        with self._lock:
            peaks, self._peaks = self._peaks, {}
        return peaks

    def stop(self):
        """Thread-safe; the thread disconnects every stream and closes the connection."""
        with self._lock:
            self._stopping = True
            self._wake()

    def _wake(self):
        if self._loop is not None:
            c.pa.mainloop_wakeup(self._loop)

    # --- meter thread ---

    def run(self):
        try:
            pulse = pulsectl.Pulse("gtk-widgets-audio-meters")
        except Exception:
            return  # the event connection notices a dead server and reconnects
        self._proplist = c.pa.proplist_from_string(f"application.id={APP_ID}")
        with self._lock:
            self._loop = pulse._loop
        try:
            while True:
                with self._lock:
                    if self._stopping:
                        break
                    targets, self._targets = self._targets, None
                if targets is not None:
                    self._apply(pulse, targets)
                # mainloop_wakeup() from set_targets()/stop() ends a blocking iterate
                c.pa.mainloop_iterate(pulse._loop, 1, None)
                if not pulse.connected:
                    break
                if self._closing:
                    self._reap()
        except c.pa.CallError:
            pass  # mainloop error: the connection is gone
        finally:
            with self._lock:
                self._loop = None
            for key in list(self._streams):
                self._close(key)
            for stream in self._closing:
                c.pa.stream_unref(stream)  # closing the connection ends them
            c.pa.proplist_free(self._proplist)
            pulse.close()

    def _apply(self, pulse, targets):
        for key in [k for k, (spec, _, _) in self._streams.items() if targets.get(k) != spec]:
            self._close(key)
        for key, spec in targets.items():
            if key not in self._streams:
                self._open(pulse, key, spec)

    def _open(self, pulse, key, spec):
        source, monitor, passive = spec
        ss = c.PA_SAMPLE_SPEC(format=c.PA_SAMPLE_FLOAT32NE, rate=METER_RATE, channels=1)
        stream = c.pa.stream_new_with_proplist(
            pulse._ctx, "Peak detect", ctypes.byref(ss), None, self._proplist)
        if not stream:
            return
        callback = c.PA_STREAM_REQUEST_CB_T(lambda s, _n, _u: self._on_read(s, key))
        attr = c.PA_BUFFER_ATTR(maxlength=2**32 - 1, fragsize=ctypes.sizeof(ctypes.c_float))
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

    def _close(self, key):
        _, stream, _ = self._streams.pop(key)
        c.pa.stream_set_read_callback(stream, _NO_CALLBACK, None)
        with self._lock:
            self._peaks.pop(key, None)
        if c.pa.stream_get_state(stream) == c.PA_STREAM_CREATING:
            # disconnect() fails until the server has created it, which would leak it
            self._closing.append(stream)
        else:
            self._release(stream)

    def _reap(self):
        for stream in [s for s in self._closing
                       if c.pa.stream_get_state(s) != c.PA_STREAM_CREATING]:
            self._closing.remove(stream)
            self._release(stream)

    @staticmethod
    def _release(stream):
        if c.pa.stream_get_state(stream) == c.PA_STREAM_READY:
            try:
                c.pa.stream_disconnect(stream)
            except c.pa.CallError:
                pass
        c.pa.stream_unref(stream)  # a failed one (device or monitored stream gone) is gone

    def _on_read(self, stream, key):
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
            peak = max(map(abs, samples), default=0.0)
        c.pa.stream_drop(stream)
        if peak < MIN_PEAK:
            return  # GTK decays meters on its own
        with self._lock:
            notify = not self._peaks
            if peak > self._peaks.get(key, 0.0):
                self._peaks[key] = peak
        if notify:
            GLib.idle_add(self._on_peaks)
