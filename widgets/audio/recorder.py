"""Test recording for input devices: record into memory, play back once, discard.

parec records the source into a pipe that a thread drains into memory, up to
MAX_SECONDS. pacat then plays the buffer on the default output. Nothing is
written to disk. Both streams carry application.id=APP_ID, so the popup hides
them like its meter streams.

State runs idle -> recording -> playing -> idle on the main thread; cancel()
returns to idle from anywhere and drops the audio. Worker threads report back
through GLib.idle_add, tagged with a generation so a cancelled run's reports
are ignored.
"""

import subprocess, threading, time

from gi.repository import GLib

from meters import APP_ID

MAX_SECONDS = 30
RATE, CHANNELS, SAMPLE_BYTES = 48000, 2, 2   # s16le stereo: ~5.5 MB for 30 s
BYTES_PER_SECOND = RATE * CHANNELS * SAMPLE_BYTES
MAX_BYTES = MAX_SECONDS * BYTES_PER_SECOND
# Low latency: little is lost when parec is stopped, little plays on after pacat is killed.
STREAM_ARGS = ["--raw", "--format=s16le", f"--rate={RATE}", f"--channels={CHANNELS}",
               "--latency-msec=50", f"--property=application.id={APP_ID}",
               "--stream-name=Test recording"]


class Recorder:
    """At most one test recording at a time. on_change() runs after every state change."""

    def __init__(self, on_change):
        self._on_change = on_change
        self.state = "idle"        # idle | recording | playing
        self.source = None         # pulse index of the source being recorded or played back
        self._proc = None
        self._gen = 0
        self._started = 0.0
        self._length = 0.0         # seconds recorded, while playing

    def seconds(self):
        """Elapsed while recording, remaining while playing."""
        elapsed = time.monotonic() - self._started
        if self.state == "playing":
            return max(self._length - elapsed, 0.0)
        return min(elapsed, MAX_SECONDS)

    def record(self, source_name, source_index):
        self.cancel()
        try:
            proc = subprocess.Popen(["parec", f"--device={source_name}", *STREAM_ARGS],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            return  # libpulse's parec missing
        self._proc, self.state, self.source = proc, "recording", source_index
        self._started = time.monotonic()
        threading.Thread(target=self._drain, args=(proc, self._gen), daemon=True).start()
        self._on_change()

    def stop(self):
        """Recording: stop and play it back. Playing: stop and discard."""
        if self.state == "recording":
            self._proc.terminate()  # the drain thread sees EOF and hands the audio over
        elif self.state == "playing":
            self.cancel()

    def cancel(self):
        self._gen += 1
        if self._proc is not None:
            self._proc.kill()
            self._proc = None
        if self.state != "idle":
            self.state, self.source = "idle", None
            self._on_change()

    # --- worker threads ---

    def _drain(self, proc, gen):
        buf = bytearray()
        while len(buf) < MAX_BYTES:
            chunk = proc.stdout.read1(65536)
            if not chunk:
                break
            buf += chunk
        proc.kill()  # at the cap it is still running
        proc.wait()
        del buf[MAX_BYTES - MAX_BYTES % (CHANNELS * SAMPLE_BYTES):]
        GLib.idle_add(self._recorded, gen, bytes(buf))

    @staticmethod
    def _feed(proc, data, done):
        try:
            proc.stdin.write(data)
            proc.stdin.close()
        except (BrokenPipeError, ValueError):
            pass  # killed by cancel()
        proc.wait()
        GLib.idle_add(done)

    # --- main thread ---

    def _recorded(self, gen, data):
        if gen != self._gen:
            return GLib.SOURCE_REMOVE
        self._proc = None
        if not data:
            self.cancel()  # parec failed (device gone) or stopped at once
            return GLib.SOURCE_REMOVE
        try:
            proc = subprocess.Popen(["pacat", "--playback", *STREAM_ARGS],
                                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        except OSError:
            self.cancel()
            return GLib.SOURCE_REMOVE
        self._proc, self.state = proc, "playing"
        self._length, self._started = len(data) / BYTES_PER_SECOND, time.monotonic()
        threading.Thread(target=self._feed, args=(proc, data, lambda: self._played(gen)),
                         daemon=True).start()
        self._on_change()
        return GLib.SOURCE_REMOVE

    def _played(self, gen):
        if gen == self._gen:
            self._proc = None
            self.cancel()
        return GLib.SOURCE_REMOVE
