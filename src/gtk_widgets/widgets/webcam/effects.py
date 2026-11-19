"""webcam-effects: the background effects engine. ffmpeg decodes the camera,
Robust Video Matting (ONNX Runtime, CPU) finds the person, numpy puts them
over a blurred picture, an image, a looped GIF or video, or a colour, and a
second ffmpeg writes the
result to the v4l2loopback device that apps pick as their camera. The only
module allowed numpy and onnxruntime (Arch's python-numpy and
python-onnxruntime-cpu): it runs as its own process.

The settings file is read again when it changes, so the popup switches the
effect while the engine runs. Exit 0 stopped, 1 already running, 2 an error."""

import contextlib
import fcntl
import hashlib
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from types import FrameType
from typing import IO

import numpy as np
import numpy.typing as npt
import onnxruntime as ort

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.widgets.webcam import engine, links, settings, v4l2
from gtk_widgets.widgets.webcam.parse import DEFAULT_COLOUR, Effect, Settings

type Frame = npt.NDArray[np.uint8]  # H x W x 3 RGB
type Alpha = npt.NDArray[np.float32]  # H x W, 1 = person
type Wide = npt.NDArray[np.uint16]  # a frame or weights, room for products

WIDTH, HEIGHT, FPS = 1280, 720, 30
FRAME_BYTES = WIDTH * HEIGHT * 3
# RVM sees every second pixel (640x360); it finds the person at 0.375 of
# that and refines the edges back at 640x360. The matte is then doubled.
# Measured on the Ryzen 7 8845HS: ~8 ms a frame on 8 threads (16 is slower).
MODEL_STEP = 2
DOWNSAMPLE = 0.375
MODEL_THREADS = 8
ALPHA_ONE = 256  # the matte in integer steps: 256 = person
MODEL_URL = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx"
MODEL_SHA256 = "88d4531297118f595bf2fd60f6f566aec2e559393802d1f436c380f0cbbd2828"
MODEL_FILE = Path.home() / ".cache/gtk-widgets/webcam/rvm_mobilenetv3_fp32.onnx"
DOWNLOAD_NAME = "video.%(ext)s"
PARTIAL_SUFFIXES = {".part", ".ytdl"}  # yt-dlp's files while it downloads
SETTINGS_CHECK_S = 0.5
FFMPEG_EXIT_S = 2
BLUR_SHRINK = 4  # of the model's half-size frame: blurred at 160x90
MAX_BLUR_RADIUS = 6  # box radius at 1/8 size, three passes ~ a Gaussian
BLUR_PASSES = 3
BLUR_EVERY = 2
LINK_RETRY_S = 5.0
LINK_RETRY_MAX_S = 60.0


def _downloads() -> Path:
    """Copies of links that cannot play from a pipe, one folder per player,
    deleted when it stops (and at start, after a crash)."""
    return Path.home() / ".cache/gtk-widgets/webcam/downloads"


class EngineError(RuntimeError):
    """The engine cannot run: no camera, no loopback device, no model."""


def _model() -> Path:
    """The model file, downloaded once and checked against its hash."""
    if MODEL_FILE.exists():
        return MODEL_FILE
    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {MODEL_URL}", file=sys.stderr, flush=True)
    with urllib.request.urlopen(MODEL_URL, timeout=60) as response:
        data: bytes = response.read()
    if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
        msg = "the downloaded model's hash does not match"
        raise EngineError(msg)
    tmp = MODEL_FILE.with_suffix(".part")
    _ = tmp.write_bytes(data)
    _ = tmp.replace(MODEL_FILE)
    return MODEL_FILE


class Matte:
    """Robust Video Matting: a person's alpha matte per frame. It is recurrent:
    each frame's state goes into the next, which keeps edges steady."""

    def __init__(self, model: Path) -> None:
        options = ort.SessionOptions()
        options.intra_op_num_threads = min(os.cpu_count() or 1, MODEL_THREADS)
        # ORT's threads spin between runs by default: ~8 cores busy at 30 fps
        # for no faster matte (measured 2026-11-18: 770% CPU, 200% without)
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        options.add_session_config_entry("session.inter_op.allow_spinning", "0")
        self._session = ort.InferenceSession(
            str(model), options, providers=["CPUExecutionProvider"]
        )
        self.reset()

    def reset(self) -> None:
        self._state = [np.zeros((1, 1, 1, 1), np.float32) for _ in range(4)]

    def alpha(self, small: Frame) -> Alpha:
        src = (small.astype(np.float32) / 255).transpose(2, 0, 1)[np.newaxis]
        r1, r2, r3, r4 = self._state
        outputs = self._session.run(
            None,
            {
                "src": src,
                "r1i": r1,
                "r2i": r2,
                "r3i": r3,
                "r4i": r4,
                "downsample_ratio": np.array([DOWNSAMPLE], np.float32),
            },
        )
        # outputs: fgr, pha, r1o..r4o
        self._state = [np.asarray(o, np.float32) for o in outputs[2:6]]
        return np.asarray(outputs[1], np.float32)[0, 0]


def _shrink(frame: Frame, factor: int) -> npt.NDArray[np.float32]:
    """Means of factor x factor blocks: integer sums, rows then columns
    (faster than one mean over both, and exact)."""
    h, w = frame.shape[0] // factor, frame.shape[1] // factor
    rows = frame[: h * factor, : w * factor].reshape(h, factor, w * factor, -1)
    summed = rows.sum(axis=1, dtype=np.uint16).reshape(h, w, factor, -1)
    total = summed.sum(axis=2, dtype=np.uint16).astype(np.float32)
    return total / np.float32(factor**2)


def _grow(
    small: npt.NDArray[np.float32], width: int, height: int
) -> npt.NDArray[np.float32]:
    """Bilinear scale up to width x height."""

    def axis(
        n_in: int, n_out: int
    ) -> tuple[npt.NDArray[np.intp], npt.NDArray[np.intp], npt.NDArray[np.float32]]:
        pos = np.clip(
            (np.arange(n_out, dtype=np.float32) + 0.5) * n_in / n_out - 0.5, 0, n_in - 1
        )
        lo = np.floor(pos).astype(np.intp)
        hi = np.minimum(lo + 1, n_in - 1)
        return lo, hi, (pos - lo).astype(np.float32)

    # Each pass gathers whole rows (a column gather is several times slower):
    # rows, then the columns as rows of the transposed result
    y0, y1, wy = axis(small.shape[0], height)
    x0, x1, wx = axis(small.shape[1], width)
    shape = (-1, 1) + (1,) * (small.ndim - 2)
    rows = small[y0] * (1 - wy.reshape(shape)) + small[y1] * wy.reshape(shape)
    cols = np.ascontiguousarray(np.swapaxes(rows, 0, 1))
    grown = cols[x0] * (1 - wx.reshape(shape)) + cols[x1] * wx.reshape(shape)
    return np.swapaxes(grown.astype(np.float32, copy=False), 0, 1)


def _box_blur(img: npt.NDArray[np.float32], radius: int) -> npt.NDArray[np.float32]:
    """A box blur of `radius` along both axes, edges repeated."""
    for axis in (0, 1):
        pad = [(0, 0)] * img.ndim
        pad[axis] = (radius + 1, radius)
        padded = np.pad(img, pad, mode="edge")
        summed = np.cumsum(padded, axis=axis, dtype=np.float32)
        n = img.shape[axis]
        hi = np.take(
            summed,
            np.arange(2 * radius + 1, 2 * radius + 1 + n, dtype=np.intp),
            axis=axis,
        )
        lo = np.take(summed, np.arange(n, dtype=np.intp), axis=axis)
        img = ((hi - lo) / (2 * radius + 1)).astype(np.float32, copy=False)
    return img


def _double(img: npt.NDArray[np.uint16]) -> npt.NDArray[np.uint16]:
    """Each pixel as 2x2: the half-size matte and background to full size."""
    return np.repeat(np.repeat(img, 2, axis=0), 2, axis=1)


def _blurred(half: Frame, strength: float) -> Wide:
    small = _shrink(half, BLUR_SHRINK)
    radius = max(round(strength * MAX_BLUR_RADIUS), 1)
    for _ in range(BLUR_PASSES):
        small = _box_blur(small, radius)
    grown = _grow(small, WIDTH // MODEL_STEP, HEIGHT // MODEL_STEP)
    # C order: _double on the transposed view is ~8 ms slower
    return _double(grown.astype(np.uint16, order="C"))


def _colour(hex_rgb: str) -> Wide:
    try:
        rgb = bytes.fromhex(hex_rgb)
    except ValueError:
        rgb = bytes.fromhex(DEFAULT_COLOUR)
    if len(rgb) != len("rgb"):
        rgb = bytes.fromhex(DEFAULT_COLOUR)
    # A whole frame, not a broadcast view: the blend is ~5 ms faster on it
    return np.full((HEIGHT, WIDTH, 3), list(rgb), np.uint16)


# Fills the frame, cropped to the picture's aspect
FILL = (
    f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT}"
)


def _image(path: str) -> Wide | None:
    """The image filling the frame, decoded by ffmpeg."""
    done = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            path,
            "-vf",
            FILL,
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if done.returncode != 0 or len(done.stdout) != FRAME_BYTES:
        print(f"background image not read: {path}", file=sys.stderr, flush=True)
        return None
    return (
        np.frombuffer(done.stdout, np.uint8).reshape(HEIGHT, WIDTH, 3).astype(np.uint16)
    )


class Animation:
    """A GIF, video or link looped at its own speed and frame rate (at most
    FPS); latest() is the newest frame. A frame is held until the next one
    comes, so the clip plays at its real speed while the camera's frames
    come at theirs. Everything runs on its own thread: a link takes seconds
    to start, and the engine's loop never waits on it.

    A link is downloaded by yt-dlp into ffmpeg's stdin: YouTube refuses the
    stream's URL to anything but yt-dlp's own downloader (403). A pipe does
    not loop, so the link starts again when its video ends; one that shows
    no frame is tried again after LINK_RETRY_S, doubling up to
    LINK_RETRY_MAX_S."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._frame: Wide | None = None
        self._closed = threading.Event()
        self._lock = threading.Lock()  # guards _children against close()
        self._children: list[subprocess.Popen[bytes]] = []
        self._as_chrome: tuple[str, ...] = ()  # links.IMPERSONATE after a 403
        self._thread = threading.Thread(target=self._play, daemon=True)
        self._thread.start()

    def latest(self) -> Wide | None:
        return self._frame

    def close(self) -> None:
        """Stop without waiting: the engine's loop calls it, and ffmpeg takes
        ~0.5 s to end a network read. The thread reaps the children: it
        drains the pipe, so none is blocked on it and each ends on SIGTERM."""
        self._closed.set()
        with self._lock:
            children = list(self._children)
        for child in children:
            child.terminate()

    def _spawn(
        self, argv: list[str], stdin: IO[bytes] | None = None
    ) -> subprocess.Popen[bytes] | None:
        with self._lock:
            if self._closed.is_set():
                return None
            try:
                child = subprocess.Popen(
                    argv,
                    stdin=subprocess.DEVNULL if stdin is None else stdin,
                    stdout=subprocess.PIPE,
                    # A file's ffmpeg errors go to the log. A link's would be
                    # the log's last line, which the popup shows as why the
                    # engine stopped (yt-dlp's warnings; ffmpeg's "-" on an
                    # empty pipe): _play_link reads yt-dlp's and says what
                    # failed
                    stderr=subprocess.PIPE
                    if argv[0] == "yt-dlp"
                    else None
                    if stdin is None
                    else subprocess.DEVNULL,
                )
            except OSError as e:  # the tool is not installed
                print(
                    f"background: {argv[0]}: {e.strerror}", file=sys.stderr, flush=True
                )
                return None
            self._children.append(child)
            return child

    def _play(self) -> None:
        if not links.is_link(Path(self._path)):
            # A file loops by itself: it ends on an error, or on close()
            self._read(["-stream_loop", "-1", "-i", self._path])
            self._reap()
            if not self._closed.is_set():
                print(f"background not read: {self._path}", file=sys.stderr, flush=True)
            return
        retry = LINK_RETRY_S
        while not self._closed.is_set():
            if self._play_link():
                retry = LINK_RETRY_S  # it played to its end: start it again
            elif self._closed.wait(retry):
                return
            else:
                retry = min(retry * 2, LINK_RETRY_MAX_S)

    def _play_link(self) -> bool:
        """Play the link once to its end; whether it showed a frame."""
        match links.load_link(Path(self._path)):
            case ParseError() as e:
                print(f"background link: {e}", file=sys.stderr, flush=True)
                return False
            case link:
                pass
        download = self._spawn(links.download_argv(link, "-", *self._as_chrome))
        if download is None or download.stdout is None:
            return False
        played = self._read(["-i", "-"], stdin=download.stdout)
        download.stdout.close()
        self._reap()
        said = _said(download)
        if not played and not self._closed.is_set():
            if not self._as_chrome and links.refused(said):
                self._as_chrome = links.IMPERSONATE
                return self._play_link()
            if links.cannot_impersonate(said):
                print(
                    f"background link: {link}: {links.NEEDS_CURL_CFFI}",
                    file=sys.stderr,
                    flush=True,
                )
                return False
            # An MP4 with its index at the end (no faststart) gives no frame
            # from a pipe, however short: play a downloaded copy
            played = self._play_copy(link)
        if not played and not self._closed.is_set():
            print(f"background link not played: {link}", file=sys.stderr, flush=True)
        return played

    def _play_copy(self, link: str) -> bool:
        """Download the link to a file and loop it until close() or an
        error; whether it showed a frame. The file goes when it stops."""
        try:
            _downloads().mkdir(parents=True, exist_ok=True)
            folder = Path(tempfile.mkdtemp(dir=_downloads()))
        except OSError as e:
            print(f"background link: {e}", file=sys.stderr, flush=True)
            return False
        try:
            download = self._spawn(
                links.download_argv(
                    link,
                    str(folder / DOWNLOAD_NAME),
                    *links.COPY_LIMITS,
                    *self._as_chrome,
                )
            )
            if download is None or download.stdout is None:
                return False
            _ = download.stdout.read()  # nothing (--quiet): until yt-dlp ends
            download.stdout.close()
            done = download.wait() == 0
            self._reap()
            _ = _said(download)
            files = [p for p in folder.iterdir() if p.suffix not in PARTIAL_SUFFIXES]
            if not done or len(files) != 1:
                return False
            played = self._read(["-stream_loop", "-1", "-i", str(files[0])])
            self._reap()
            return played
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def _read(self, source: list[str], stdin: IO[bytes] | None = None) -> bool:
        """ffmpeg's frames into latest() until it ends; whether there was one."""
        proc = self._spawn(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-re",
                *source,
                "-an",
                "-vf",
                # The clip's own rate up to the engine's, dropped before the
                # scaler: a 60 fps clip is scaled 30 times a second
                f"fps=fps='min(source_fps,{FPS})',{FILL}",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            stdin,
        )
        if proc is None or proc.stdout is None:
            return False
        played = False
        with proc.stdout as out:
            while len(raw := out.read(FRAME_BYTES)) == FRAME_BYTES:
                frame = np.frombuffer(raw, np.uint8).reshape(HEIGHT, WIDTH, 3)
                self._frame = frame.astype(np.uint16)
                played = True
        return played

    def _reap(self) -> None:
        """End and wait for this run's children (yt-dlp may still be
        downloading when ffmpeg stops)."""
        with self._lock:
            children, self._children = self._children, []
        for child in children:
            _stop(child)


def _said(proc: subprocess.Popen[bytes]) -> str:
    """An ended child's errors (yt-dlp's are short: --quiet --no-warnings)."""
    if proc.stderr is None:
        return ""
    with proc.stderr as err:
        return err.read().decode(errors="replace")


def _stop(proc: subprocess.Popen[bytes]) -> None:
    proc.terminate()
    try:
        _ = proc.wait(FFMPEG_EXIT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        _ = proc.wait()


class Backgrounds:
    """The current effect's background: an image or colour made again only
    when it changes, an animation's player kept while it is the one chosen,
    a blur every BLUR_EVERY frames (what is behind the person changes
    slowly, and the blur is a third of a frame's time). A chosen picture
    that is missing, or not read yet, shows as a blur. An image is decoded
    on its own thread; one that is no longer chosen when it is ready is
    dropped."""

    def __init__(self) -> None:
        self._key: tuple[Effect, str] | None = None
        self._still: Wide | None = None
        # (path, image or None if unreadable), set by a loader thread
        self._loaded: tuple[str, Wide | None] | None = None
        self._animation: Animation | None = None
        self._animation_path = ""
        self._blur: Wide | None = None
        self._blur_age = 0

    def close(self) -> None:
        if self._animation is not None:
            self._animation.close()
            self._animation = None

    def get(self, wanted: Settings, half: Frame) -> Wide | None:
        if wanted.effect is not Effect.ANIMATED or (
            self._animation is not None and wanted.animation != self._animation_path
        ):
            self.close()
        match wanted.effect:
            case Effect.OFF:
                self._blur = None
                return None
            case Effect.ANIMATED if wanted.animation is not None:
                if self._animation is None:
                    self._animation = Animation(wanted.animation)
                    self._animation_path = wanted.animation
                background = self._animation.latest()
            case Effect.IMAGE if wanted.image is not None:
                background = self._fixed((Effect.IMAGE, wanted.image))
            case Effect.COLOUR:
                background = self._fixed((Effect.COLOUR, wanted.colour))
            case Effect.BLUR | Effect.IMAGE | Effect.ANIMATED:
                background = None
        return (
            background if background is not None else self._blurred(half, wanted.blur)
        )

    def _fixed(self, key: tuple[Effect, str]) -> Wide | None:
        """The chosen image or colour, None while an image is not read yet."""
        if key != self._key:
            self._key = key
            if key[0] is Effect.IMAGE:
                # Decoding takes 2-4 frames: the old background stays until then
                threading.Thread(target=self._load, args=(key[1],), daemon=True).start()
            else:
                self._still = _colour(key[1])
        if key[0] is Effect.IMAGE and (loaded := self._loaded) and loaded[0] == key[1]:
            self._still, self._loaded = loaded[1], None
        return self._still

    def _load(self, path: str) -> None:
        self._loaded = (path, _image(path))

    def _blurred(self, half: Frame, strength: float) -> Wide:
        self._blur_age += 1
        if self._blur is None or self._blur_age >= BLUR_EVERY:
            self._blur, self._blur_age = _blurred(half, strength), 0
        return self._blur


def _reader(camera: Path) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "v4l2",
            "-input_format",
            "mjpeg",
            "-video_size",
            f"{WIDTH}x{HEIGHT}",
            "-framerate",
            str(FPS),
            "-i",
            str(camera),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
    )


def _writer(loopback: Path) -> subprocess.Popen[bytes]:
    # YUYV: the format every app takes from a V4L2 camera
    return subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-video_size",
            f"{WIDTH}x{HEIGHT}",
            "-framerate",
            str(FPS),
            "-i",
            "-",
            # One thread converts a frame in ~1 ms less CPU than several
            "-threads",
            "1",
            "-f",
            "v4l2",
            "-pix_fmt",
            "yuyv422",
            str(loopback),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
    )


class WatchedSettings:
    """The settings file, read again when it changes."""

    def __init__(self) -> None:
        self.current = Settings()
        self._stamp: tuple[int, int] | None = None
        self._checked = 0.0

    def poll(self) -> None:
        now = time.monotonic()
        if now - self._checked < SETTINGS_CHECK_S:
            return
        self._checked = now
        # Each save renames a new file in: its inode tells two saves within
        # one mtime tick apart
        try:
            st = settings.SETTINGS_FILE.stat()
            stamp = (st.st_ino, st.st_mtime_ns)
        except OSError:
            stamp = (0, 0)
        if stamp == self._stamp:
            return
        self._stamp = stamp
        match settings.load():
            case ParseError() as e:
                print(f"settings not read: {e}", file=sys.stderr, flush=True)
            case loaded:
                self.current = loaded


class Compositor:
    """Puts the person over the background in buffers made once: a frame's
    worth of new arrays each frame cost more than the blend itself. The
    returned view is overwritten by the next call."""

    def __init__(self) -> None:
        shape = (HEIGHT, WIDTH, 3)
        self._person = np.empty(shape, np.uint16)
        self._rest = np.empty(shape, np.uint16)
        self._sum = np.empty(shape, np.uint16)
        self._out = np.empty(shape, np.uint8)

    def __call__(
        self,
        frame: Frame,
        wanted: Settings,
        backgrounds: Backgrounds,
        matte: Matte,
        *,
        fresh: bool,
    ) -> memoryview | None:
        """The frame with its background replaced; None when the effect is
        off. `fresh`: the previous frame had no effect, so the matte's state
        is stale."""
        half = np.ascontiguousarray(frame[::MODEL_STEP, ::MODEL_STEP])
        background = backgrounds.get(wanted, half)
        if background is None:
            return None
        if fresh:
            matte.reset()
        weight = np.rint(matte.alpha(half) * ALPHA_ONE).astype(np.uint16)
        # Each half-size weight to its 2x2 pixels and their 3 channels
        h, w = weight.shape
        self._person.reshape(h, MODEL_STEP, w, MODEL_STEP * 3)[...] = weight[
            :, np.newaxis, :, np.newaxis
        ]
        # frame * person + background * (ALPHA_ONE - person), >> 8: at most
        # 255 * 256, so uint16 holds it
        _ = np.multiply(frame, self._person, out=self._sum)
        _ = np.subtract(ALPHA_ONE, self._person, out=self._rest)
        self._rest *= background
        self._sum += self._rest
        self._sum >>= ALPHA_ONE.bit_length() - 1
        np.copyto(self._out, self._sum, casting="unsafe")
        return memoryview(self._out).cast("B")


def run(camera: Path, loopback: Path, stop: list[bool]) -> None:
    matte = Matte(_model())
    backgrounds = Backgrounds()
    composite = Compositor()
    watched = WatchedSettings()
    reader, writer = _reader(camera), _writer(loopback)
    flipped: Frame = np.empty((HEIGHT, WIDTH, 3), np.uint8)

    def on_signal(_sig: int, _frame: FrameType | None) -> None:
        # The read below is retried after a signal (PEP 475) and a camera
        # that sends nothing never returns it: the reader's end does
        stop[0] = True
        reader.kill()

    _ = signal.signal(signal.SIGTERM, on_signal)
    _ = signal.signal(signal.SIGINT, on_signal)
    try:
        src, sink = reader.stdout, writer.stdin
        if src is None or sink is None:
            msg = "ffmpeg pipes missing"
            raise EngineError(msg)
        print(f"{camera} -> {loopback}", file=sys.stderr, flush=True)
        was_on, was_mirrored = False, False
        while not stop[0] and len(raw := src.read(FRAME_BYTES)) == FRAME_BYTES:
            watched.poll()
            wanted = watched.current
            frame: Frame = np.frombuffer(raw, np.uint8).reshape(HEIGHT, WIDTH, 3)
            if wanted.mirror_output:
                np.copyto(flipped, frame[:, ::-1])
                frame = flipped
            # The matte's state follows the person: a flip moves them
            fresh = not was_on or wanted.mirror_output != was_mirrored
            out = composite(frame, wanted, backgrounds, matte, fresh=fresh)
            was_on, was_mirrored = out is not None, wanted.mirror_output
            if out is not None:
                sink.write(out)
            elif wanted.mirror_output:
                sink.write(memoryview(flipped).cast("B"))
            else:
                sink.write(raw)
        if not stop[0]:
            raise EngineError(f"{camera}: the camera stopped (in use by another app?)")
    finally:
        # Our pipe ends first: an ffmpeg blocked on a full or empty pipe
        # ignores SIGTERM until the pipe breaks
        for pipe in (reader.stdout, writer.stdin):
            with contextlib.suppress(OSError):
                if pipe is not None:
                    pipe.close()
        for proc in (reader, writer):
            _stop(proc)
        backgrounds.close()


def main(argv: list[str] | None = None) -> int:
    del argv
    lock = engine.lock_file()
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("webcam-effects: already running", file=sys.stderr)
        return 1
    os.ftruncate(fd, 0)
    _ = os.write(fd, str(os.getpid()).encode())
    shutil.rmtree(_downloads(), ignore_errors=True)  # a crashed run's copies

    stop = [False]

    def on_signal(_sig: int, _frame: FrameType | None) -> None:
        stop[0] = True

    _ = signal.signal(signal.SIGTERM, on_signal)
    _ = signal.signal(signal.SIGINT, on_signal)
    camera, loopback = v4l2.find_camera(), v4l2.find_loopback()
    if camera is None:
        print("webcam-effects: no camera", file=sys.stderr, flush=True)
        return 2
    if loopback is None:
        print(
            "webcam-effects: no v4l2loopback device: is the v4l2loopback module loaded?",
            file=sys.stderr,
            flush=True,
        )
        return 2
    try:
        run(camera, loopback, stop)
    except (EngineError, OSError) as e:
        print(f"webcam-effects: {e}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
