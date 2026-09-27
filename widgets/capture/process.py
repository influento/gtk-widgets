"""capture gif's processing, with ffmpeg only (no GTK): the full GIF, the
sheets' frames and the contact sheets, from the recording's raw.mkv.

  python3 process.py DIR [SCALE]
        run it again on DIR/raw.mkv (kept when processing failed); SCALE is
        the recorded output's scale (default 1)

make_gif() first (two decodes: the palette, then the GIF), so the GIF can be
copied while the sheets are made; make_sheets() then decodes the recording
twice more: once streaming the distinct frames at a quarter size to the
Picker, once writing the frames it kept. The same recording gives
byte-identical outputs.

The sheets are for an AI to read, and what it can read is set by how big
the text is in the image it is shown. Claude shows an image at most 2000 px
on its long edge (a 4096 px sheet was shown at 2000). In tests on random
codes it read text shown 6.5 px or more high exactly, about half of it at
4.4 px and none at 3.4 px. So a sheet is at most 2000 px, and its tiles
show each logical pixel as at least MIN_TEXT_SCALE px (10 px UI text at
6.5 px or more): frames that don't fit one sheet that way go on several.

mpdecimate compares 8x8 blocks starting at x = 8 and stepping 4, so a change
in the first 8 columns, or in a last column or row the steps don't reach,
counts as no change. Padding each frame (8 left, 8 right, 8 below) before it
and cropping after puts every pixel inside a compared block. With hi=0 (a
block differs if its SAD > 0) it then drops exact duplicates only.
"""

import math
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from collections import deque
from fractions import Fraction

_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib import theme  # noqa: E402

MIN_GAP = Fraction("0.2")  # s, the least time between two frames kept for the sheets
STATE_AREA = 30 * 30  # logical px changed since the last kept frame: a new state
BUSY_AREA = 60 * 60  # logical px changing within HOLD: the screen is busy (a pointer is less)
HOLD = Fraction("0.2")  # s the screen must hold a state for it to count
MOTION_STEP = 1  # s between frames kept while the screen never holds
SHEET_MAX_EDGE = 2000  # px, each edge of a sheet at most
MIN_TEXT_SCALE = 0.65  # px a tile shows for one logical px, at least
SWITCH_AREA = 10  # % of the frame changing at once: the screen switched (dialog, menu, page)
SWITCH_MERGE = 0.3  # s, switch frames at most this far apart are one switch (a fade)
SWITCH_LONGEST = 1  # s, a longer run of big changes is motion (scrolling, video), not a switch
DITHER = "none"  # crispest on UI text and no worse on gradients (bayer, sierra2_4a tested)
FONT = "JetBrainsMono Nerd Font"
LABEL_PX = 14  # the time labels' font size (read exactly at 10 px in the tests)
GAP_PX = 8  # padding between tiles and around them

RAW = "raw.mkv"
GIF = "recording.gif"
SHEET = "sheet.png"  # the only sheet; with several, sheet-1.png, sheet-2.png, ...
FRAMES = "frames"
_PALETTE = "palette.png"

_PAD = "pad=iw+16:ih+8:8:0"
_UNPAD = "crop=iw-16:ih-8:8:0"
EXACT = f"{_PAD},mpdecimate=hi=0:lo=0:frac=0,{_UNPAD}"  # exact duplicates only
SIMILAR = f"{_PAD},mpdecimate,{_UNPAD}"  # near duplicates too (default thresholds)
_BITEXACT = ["-fflags", "+bitexact", "-flags:v", "+bitexact"]


class ProcessError(Exception):
    pass


def _ffmpeg(args, what, cwd=None):
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", *args],
                           capture_output=True, check=False, cwd=cwd)
    except OSError as e:
        raise ProcessError(f"ffmpeg: {e}") from None
    if r.returncode:
        tail = r.stderr.decode(errors="replace").strip().splitlines()[-3:]
        raise ProcessError(f"{what} failed: " + " / ".join(tail))
    return r.stdout.decode()


def _span(raw):
    """(first frame's time, end time) of the recording, in seconds, from its
    packets (no decoding)."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=time_base:packet=pts,duration",
                            "-of", "compact=p=0:nk=0", raw], capture_output=True, text=True)
    except OSError as e:
        raise ProcessError(f"ffprobe: {e}") from None
    tb, starts, ends = None, [], []
    for line in r.stdout.splitlines():
        fields = dict(f.split("=", 1) for f in line.split("|") if "=" in f)
        if "time_base" in fields:
            tb = Fraction(fields["time_base"])
        elif fields.get("pts", "N/A") != "N/A":
            pts = int(fields["pts"])
            dur = int(fields["duration"]) if fields.get("duration", "N/A") != "N/A" else 0
            starts.append(pts)
            ends.append(pts + dur)
    if r.returncode or tb is None or not starts:
        raise ProcessError(f"{raw} has no frames")
    return min(starts) * tb, max(ends) * tb


_QUANTISE = bytes(v >> 4 for v in range(256))  # 16 levels: small shading changes don't count


def changed(a, b, size):
    """How many of two quantised frames' size pixels differ (the frames as
    ints: XOR and counting zero bytes run in C)."""
    x = a ^ b
    return size - x.to_bytes(size, "big").count(0) if x else 0


_EPS = Fraction(1, 1000)


class Picker:
    """Chooses the sheets' frames as they stream in (quarter size, gray,
    quantised; see changed()), from the distinct frames' times.

    A frame is kept when it shows a new state: STATE_AREA logical px or more
    changed since the last kept frame, and the screen then holds (nothing
    changes by BUSY_AREA for HOLD s: a moving pointer doesn't count, a fade
    does), MIN_GAP after the last kept one. While the screen keeps changing
    for over SWITCH_LONGEST (scrolling, video, a battle) it takes one frame
    every MOTION_STEP. The frame just before each switch (SWITCH_AREA % of
    the region changing at once, after SWITCH_MERGE s without one) is always
    kept: a state's last look, which shows what was clicked. So is the first
    and the last frame. There is no cap: the tiles follow the content."""

    def __init__(self, size, scale):
        self.size = size
        unit = scale * scale / 16  # a quarter-size pixel is 16 / scale^2 logical px
        self.state = STATE_AREA * unit
        self.busy = BUSY_AREA * unit
        self.pending = deque()  # (index, time, frame), waiting for HOLD s of what follows
        self.prev = None
        self.last_switch = None
        self.busy_since = None
        self.last = None  # the last kept (index, time, frame)
        self.kept = []
        self.before = set()  # frames just before a switch
        self.count = 0

    def add(self, t, frame):
        i = self.count
        self.count += 1
        if self.prev is not None:
            if changed(frame, self.prev, self.size) * 100 >= SWITCH_AREA * self.size:
                if self.last_switch is None or t - self.last_switch > SWITCH_MERGE:
                    self.before.add(i - 1)
                self.last_switch = t
        self.prev = frame
        self.pending.append((i, t, frame))
        while self.pending[0][1] + HOLD <= t:
            self._decide(*self.pending.popleft())

    def finish(self):
        """The kept frames' indices, and which of them come just before a switch."""
        while self.pending:
            last = self.pending[0][0] == self.count - 1
            self._decide(*self.pending.popleft())
            if last and self.kept[-1] != self.count - 1:
                self.kept.append(self.count - 1)
        return self.kept, self.before & set(self.kept)

    def _decide(self, i, t, frame):
        holds = all(changed(frame, f, self.size) < self.busy
                    for _, u, f in self.pending if u - t < HOLD)
        if holds:
            self.busy_since = None
        elif self.busy_since is None:
            self.busy_since = t
        if self.last is None:
            return self._keep(i, t, frame)
        gap = t - self.last[1]
        if i in self.before:
            if gap >= _EPS:
                self._keep(i, t, frame)
            return
        if changed(frame, self.last[2], self.size) < self.state:
            return
        if holds:
            if gap >= MIN_GAP:
                self._keep(i, t, frame)
        elif gap >= MOTION_STEP and t - self.busy_since >= SWITCH_LONGEST:
            self._keep(i, t, frame)

    def _keep(self, i, t, frame):
        self.kept.append(i)
        self.last = (i, t, frame)


def label(t):
    return f"{t:06.3f}s"


BEFORE_SWITCH = "before switch"


def tile_label(index, count, t, before_switch=False):
    """A tile's label: its place among all the sheets' tiles (so the sheets
    need no legend, and a missing one shows), its time, and whether the
    screen switches right after it (the pointer shows what was clicked)."""
    parts = [f"{index}/{count}", label(t)] + ([BEFORE_SWITCH] if before_switch else [])
    return " · ".join(parts)


class Layout:
    """One sheet's geometry for count frames of w x h: cols x rows cells of
    cell_w x cell_h (the frame shrunk by scale to tile_w x tile_h, outlined,
    under a label strip of strip px), gap px between and around them, to
    width x height. Of the grids that fit max_edge, the one with the biggest
    tiles; ties (tiles at full size) go to the sheet closest to square, then
    to fewer empty cells. scale is 0 when none fits."""

    font = LABEL_PX
    strip = math.ceil(LABEL_PX * 1.5)
    gap = GAP_PX
    # "300/300 · 60.000s · before switch" in a monospace font, with room
    label_w = math.ceil(LABEL_PX * 0.62 * (len(tile_label(300, 300, 60, True)) + 1))

    def __init__(self, count, w, h, max_edge=SHEET_MAX_EDGE):
        best = None
        for cols in range(1, count + 1):
            rows = math.ceil(count / cols)
            room_w = (max_edge - (cols + 1) * self.gap) // cols
            room_h = (max_edge - (rows + 1) * self.gap) // rows - self.strip
            if room_w < self.label_w or room_h < 3:
                continue
            self._grid(cols, rows, min(1.0, (room_w - 2) / w, (room_h - 2) / h), w, h)
            key = (-self.scale, abs(math.log(self.width / self.height)), cols * rows - count)
            if best is None or key < best[0]:
                best = (key, cols, rows, self.scale)
        self._grid(*(best[1:] if best else (1, count, 0.0)), w, h)

    def _grid(self, cols, rows, scale, w, h):
        self.cols, self.rows, self.scale = cols, rows, scale
        # At least 1 px, and never past the room: floor, not round
        self.tile_w = max(1, math.floor(w * scale))
        self.tile_h = max(1, math.floor(h * scale))
        self.cell_w = max(self.tile_w + 2, self.label_w)
        self.cell_h = self.tile_h + 2 + self.strip
        self.width = cols * self.cell_w + (cols + 1) * self.gap
        self.height = rows * self.cell_h + (rows + 1) * self.gap


def split(count, w, h, min_scale, max_edge=SHEET_MAX_EDGE):
    """How many of count frames of w x h go on each sheet: as few sheets as
    keep the tiles at min_scale or bigger (one frame a sheet at the least),
    the frames spread evenly, earlier sheets taking the odd ones."""
    for k in range(1, count + 1):
        if k == count or Layout(math.ceil(count / k), w, h, max_edge).scale >= min_scale:
            return [count // k + (i < count % k) for i in range(k)]
    return []


def sheet_names(n):
    """The file names of n sheets."""
    if n == 1:
        return [SHEET]
    stem, ext = os.path.splitext(SHEET)
    return [f"{stem}-{i}{ext}" for i in range(1, n + 1)]


def frame_name(index, t):
    """frames/ file name: 1-based index and time, e.g. 0001-00.000s.png."""
    return f"{index:04d}-{label(t)}.png"


def _clean(folder, gif=True, sheets=True):
    """Remove what an earlier run left: the GIF, the sheets and frames/."""
    stem, ext = os.path.splitext(SHEET)
    for name in os.listdir(folder):
        if ((gif and name in (GIF, _PALETTE))
                or (sheets and (name == SHEET or (name.startswith(stem + "-") and name.endswith(ext))))):
            os.remove(os.path.join(folder, name))
    if sheets:
        shutil.rmtree(os.path.join(folder, FRAMES), ignore_errors=True)


def process(folder, scale=1, colors=None):
    """make_gif(), then make_sheets(); returns make_sheets()'s result."""
    make_gif(folder)
    return make_sheets(folder, scale, colors)


def make_gif(folder):
    """Turn folder/raw.mkv into folder/recording.gif (every frame, exact
    duplicates merged). Returns its path. Raises ProcessError."""
    folder = os.path.abspath(folder)
    raw = _raw(folder)
    _clean(folder, sheets=False)
    t0, end = _span(raw)
    palette = os.path.join(folder, _PALETTE)
    gif = os.path.join(folder, GIF)
    try:
        _ffmpeg(["-i", raw, "-vf", f"{EXACT},palettegen=stats_mode=diff", *_BITEXACT,
                 "-frames:v", "1", "-update", "1", palette], "making the GIF's palette")
        _ffmpeg(["-i", raw, "-i", palette, "-filter_complex",
                 f"[0:v]{EXACT}[g];[g][1:v]paletteuse=dither={DITHER}:diff_mode=rectangle",
                 "-fps_mode", "passthrough", "-loop", "0", *_BITEXACT, gif],
                "writing the GIF")
    finally:
        if os.path.exists(palette):
            os.remove(palette)
    set_duration(gif, end - t0)
    return gif


def make_sheets(folder, scale=1, colors=None):
    """Turn folder/raw.mkv, recorded on an output of this scale, into the
    sheets' frames (see Picker) and the sheets, then delete raw.mkv. Returns
    {"distinct": n, "frames": [(name, time)], "sheets": [path]}. Raises
    ProcessError; raw.mkv is kept then."""
    folder = os.path.abspath(folder)
    raw = _raw(folder)
    colors = colors or theme.colors()
    _clean(folder, gif=False)
    t0 = _span(raw)[0]
    w, h = _size(raw)

    # 1: the frames that differ, streamed to the Picker at a quarter size
    times, kept, before = _analyse(raw, w, h, scale)
    times = [t - t0 for t in times]

    # 2: the kept frames
    frames = os.path.join(folder, FRAMES)
    os.makedirs(frames)
    select = "+".join(f"eq(n,{i})" for i in kept)
    _ffmpeg(["-i", raw, "-vf", f"{SIMILAR},select='{select}'", "-fps_mode", "passthrough",
             *_BITEXACT, "-start_number", "1", os.path.join(frames, "%04d.png")],
            "writing the frames")
    names, tiles = [], []
    for n, i in enumerate(kept, 1):
        name = frame_name(n, times[i])
        os.rename(os.path.join(frames, f"{n:04d}.png"), os.path.join(frames, name))
        names.append((name, times[i]))
        tiles.append((name, tile_label(n, len(kept), times[i], i in before)))

    # 3: the sheets
    counts = split(len(names), w, h, min(1.0, MIN_TEXT_SCALE / scale))
    sheets, first = [], 0
    for name, count in zip(sheet_names(len(counts)), counts):
        sheets.append(os.path.join(folder, name))
        sheet(frames, tiles[first:first + count], (w, h), sheets[-1], colors)
        first += count
    os.remove(raw)
    return {"distinct": len(times), "frames": [(n, float(t)) for n, t in names],
            "sheets": sheets}


def _raw(folder):
    raw = os.path.join(folder, RAW)
    if not os.path.isfile(raw):
        raise ProcessError(f"{raw} is missing")
    return raw


def _analyse(raw, w, h, scale):
    """One decode, streamed to the Picker: the distinct frames at a quarter
    size on stdout and their times (a framemd5 listing) on a second pipe,
    each drained by its own thread so ffmpeg never waits on either.
    Returns (times, kept indices, those just before a switch)."""
    qw, qh = -(-w // 4), -(-h // 4)
    size = qw * qh
    picker = Picker(size, scale)
    times_r, times_w = os.pipe()
    with tempfile.TemporaryFile() as err:
        try:
            proc = subprocess.Popen(
                ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-i", raw,
                 "-filter_complex",
                 f"[0:v]{SIMILAR},split[s][q];[q]scale={qw}:{qh}:flags=area,format=gray[g]",
                 "-map", "[s]", "-fps_mode", "passthrough", "-flush_packets", "1",
                 "-f", "framemd5", f"pipe:{times_w}",
                 "-map", "[g]", "-fps_mode", "passthrough", "-f", "rawvideo", "pipe:1"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err,
                pass_fds=(times_w,))
        except OSError as e:
            os.close(times_r)
            raise ProcessError(f"ffmpeg: {e}") from None
        finally:
            os.close(times_w)
        times, frames = queue.SimpleQueue(), queue.Queue(maxsize=32)

        def read_times():
            tb = None
            with open(times_r) as f:
                for line in f:
                    if line.startswith("#tb 0:"):
                        tb = Fraction(line.split(":", 1)[1].strip())
                    elif line.strip() and not line.startswith("#"):
                        times.put(int(line.split(",")[2]) * tb)
            times.put(None)

        def read_frames():
            while len(buf := proc.stdout.read(size)) == size:
                frames.put(int.from_bytes(buf.translate(_QUANTISE), "big"))
            frames.put(None)

        readers = [threading.Thread(target=f, daemon=True) for f in (read_times, read_frames)]
        for r in readers:
            r.start()
        stamps = []
        while (frame := frames.get()) is not None:
            t = times.get()
            if t is None:  # the times ran out: let ffmpeg finish
                while frames.get() is not None:
                    pass
                break
            stamps.append(t)
            picker.add(t, frame)
        proc.wait()
        for r in readers:
            r.join()
        proc.stdout.close()
        if proc.returncode:
            err.seek(0)
            tail = err.read().decode(errors="replace").strip().splitlines()[-3:]
            raise ProcessError("reading the recording failed: " + " / ".join(tail))
    if not stamps:
        raise ProcessError("the recording has no frames")
    kept, before = picker.finish()
    return stamps, kept, before


def sheet(frames, tiles, size, path, colors):
    """Tile frames/<name> for each (name, label) in tiles, each w x h (size),
    into the sheet at path: each shrunk by the Layout's scale (area average),
    outlined (a recording of a themed app has the sheet's background) and
    under a strip with its label (see tile_label())."""
    lay = Layout(len(tiles), *size)
    base, fg, line = ("0x" + colors[k] for k in ("BASE", "TEXT", "SURFACE1"))
    shrink = (f"scale={lay.tile_w}:{lay.tile_h}:flags=area,"
              if (lay.tile_w, lay.tile_h) != tuple(size) else "")
    inputs, chains = [], []
    for k, (name, text) in enumerate(tiles):
        inputs += ["-i", os.path.join(frames, name)]
        chains.append(f"[{k}:v]format=rgb24,{shrink}pad=iw+2:ih+2:1:1:color={line},"
                      f"pad={lay.cell_w}:{lay.cell_h}:0:{lay.strip}:color={base},"
                      f"drawtext=font='{FONT}':text='{text}':fontcolor={fg}:"
                      f"fontsize={lay.font}:x=0:y=({lay.strip}-th)/2[v{k}]")
    graph = ";".join(chains) + ";" + "".join(f"[v{k}]" for k in range(len(tiles)))
    graph += (f"concat=n={len(tiles)}:v=1:a=0,"
              f"tile={lay.cols}x{lay.rows}:padding={lay.gap}:margin={lay.gap}:color={base}")
    _ffmpeg([*inputs, "-filter_complex", graph, *_BITEXACT, "-frames:v", "1", "-update", "1",
             path], "making the sheet")


def _size(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        w, h = map(int, r.stdout.strip().split(","))
    except ValueError:
        raise ProcessError(f"cannot read {path}") from None
    return w, h


def _delay_offsets(data):
    """Offsets of each image's delay field (in its Graphic Control Extension)."""
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ProcessError("not a GIF")
    p = 13
    if data[10] & 0x80:
        p += 3 << ((data[10] & 7) + 1)
    delays, pending = [], None
    while p < len(data):
        b = data[p]
        p += 1
        if b == 0x3B:  # trailer
            return delays
        if b == 0x21:  # extension: label, then sub-blocks
            if data[p] == 0xF9:
                pending = p + 3  # label, size 4, packed byte, then the delay
            p += 1
            while data[p]:
                p += data[p] + 1
            p += 1
        elif b == 0x2C:  # image descriptor, local colour table, LZW data
            packed = data[p + 8]
            p += 9
            if packed & 0x80:
                p += 3 << ((packed & 7) + 1)
            p += 1
            while data[p]:
                p += data[p] + 1
            p += 1
            delays.append(pending)
            pending = None
        else:
            raise ProcessError(f"unexpected GIF block 0x{b:02x}")
    raise ProcessError("truncated GIF")


def set_duration(path, seconds):
    """Give the GIF's last frame the rest of the recording. ffmpeg gives it
    one frame's time, so a still end (exact duplicates, dropped) would be
    cut short; its delays otherwise add up to the recording without drift."""
    with open(path, "r+b") as f:
        data = bytearray(f.read())
        offsets = _delay_offsets(data)
        if not offsets or offsets[-1] is None:
            return
        before = sum(int.from_bytes(data[o:o + 2], "little") for o in offsets[:-1])
        last = round(Fraction(seconds) * 100) - before
        if last < 1:
            return
        data[offsets[-1]:offsets[-1] + 2] = min(last, 0xFFFF).to_bytes(2, "little")
        f.seek(0)
        f.write(data)


def main(argv):
    try:
        scale = float(argv[1]) if len(argv) == 2 else 1
    except ValueError:
        scale = 0
    if len(argv) not in (1, 2) or argv[0] in ("-h", "--help") or not scale > 0:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        process(argv[0], scale)
    except (ProcessError, OSError) as e:
        print(f"capture: {e}", file=sys.stderr)
        return 2
    print(os.path.abspath(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
