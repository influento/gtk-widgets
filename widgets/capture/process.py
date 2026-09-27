"""capture gif's processing, with ffmpeg only (no GTK): the full GIF, the
sheets' frames and the contact sheets, from the recording's raw.mkv.

  python3 process.py DIR [SCALE]
        run it again on DIR/raw.mkv (kept when processing failed); SCALE is
        the recorded output's scale (default 1)

Two decodes of the recording. The first builds the GIF's palette and lists
the frames that differ from each other; the second writes the GIF and those
of the frames the sheets keep. The same recording gives byte-identical
outputs.

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
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction

_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib import theme  # noqa: E402

MIN_GAP = Fraction("0.2")  # s, the least time between two frames kept for the sheets
MAX_TILES = 30  # most frames on the sheets, all together
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


_CHANGES = "changes.txt"
# Per frame, the share of it that changed since the frame before (at a
# quarter size: switches are big), printed to _CHANGES in ffmpeg's working
# directory (a relative name needs no filtergraph escaping)
CHANGES_FILTER = ("scale=w=ceil(iw/4):h=ceil(ih/4):flags=area,format=gray,"
                  "tblend=all_mode=difference,lutyuv=y='if(gt(val\\,10)\\,255\\,0)',signalstats,"
                  f"metadata=print:key=lavfi.signalstats.YAVG:file={_CHANGES}")


def _read_changes(path):
    """(time, % of the frame changed) from CHANGES_FILTER's output."""
    out, t = [], None
    try:
        f = open(path)
    except FileNotFoundError:
        return out
    with f:
        for line in f:
            if line.startswith("frame:"):
                t = Fraction(line.rsplit("pts_time:", 1)[1].strip())
            elif line.startswith("lavfi.signalstats.YAVG=") and t is not None:
                out.append((t, float(line.split("=", 1)[1]) * 100 / 255))
    return out


def _framemd5_times(text):
    """Frame times (seconds) from ffmpeg's framemd5 listing."""
    tb, times = None, []
    for line in text.splitlines():
        if line.startswith("#tb 0:"):
            tb = Fraction(line.split(":", 1)[1].strip())
        elif line and not line.startswith("#"):
            times.append(int(line.split(",")[2]) * tb)
    return times


_EPS = Fraction(1, 1000)


def switches(changes, area=SWITCH_AREA, merge=SWITCH_MERGE):
    """The screen switches in a recording, as (start, end, peak area) out of
    (time, % of the frame changed since the frame before): frames changing
    area % or more, those at most merge s apart taken as one (a fade, an
    animated opening)."""
    out = []
    for t, a in changes:
        if a < area:
            continue
        if out and t - out[-1][1] <= merge:
            out[-1] = (out[-1][0], t, max(out[-1][2], a))
        else:
            out.append((t, t, a))
    return out


def pick(times, cuts=(), min_gap=MIN_GAP, max_tiles=MAX_TILES):
    """Indices of the frames kept for the sheets, out of the distinct frames'
    times, first and last always. Each switch in cuts (see switches()) keeps
    the frame just before it: a state's last look, which shows what was
    clicked to leave it. The rest are at least min_gap apart, and when there
    are more than max_tiles, spread over the time between those kept, none
    from inside a switch (mid-fade; a run of big changes longer than
    SWITCH_LONGEST is motion and keeps its frames). Too many switches: the
    biggest win."""
    n = len(times)
    if not n:
        return []
    spaced = [0]
    for i in range(1, n):
        if times[i] - times[spaced[-1]] >= min_gap:
            spaced.append(i)
    if spaced[-1] != n - 1:
        spaced.append(n - 1)
    before, inside = _around(times, cuts)
    anchors = {0, n - 1} | set(before)
    if len(anchors | set(spaced)) <= max_tiles:
        return sorted(anchors | set(spaced))
    if len(anchors) > max_tiles:
        ranked = sorted(before, key=lambda i: (-before[i], i))
        return sorted({0, n - 1} | set(ranked[:max_tiles - 2]))
    return sorted(_fill(times, sorted(anchors), [i for i in spaced if i not in inside],
                        max_tiles, min_gap))


def _around(times, cuts):
    """The frames just before a switch in cuts (see switches()), each with
    the switch's peak area, and the frames inside a switch no longer than
    SWITCH_LONGEST (mid-fade), as indices into the distinct frames' times."""
    n = len(times)
    before = {}
    inside = set()
    j = 0
    for start, end, peak in cuts:
        # The two listings round times differently (ms, frame steps)
        while j < n and times[j] < start - _EPS:
            j += 1
        if j:
            before[j - 1] = max(before.get(j - 1, 0), peak)
        if end - start <= SWITCH_LONGEST:
            inside.update(i for i in range(j, n) if times[i] < end - _EPS)
    return before, inside


def _fill(times, anchors, pool, max_tiles, min_gap):
    """anchors plus frames from pool up to max_tiles in all, each gap between
    anchors taking a share by its length (the largest gap per tile goes
    next) and its frames nearest to even steps across it, min_gap apart."""
    gaps = [[a, b, []] for a, b in zip(anchors, anchors[1:])]
    total = len(anchors)
    full = set()
    while total < max_tiles and len(full) < len(gaps):
        g = max((k for k in range(len(gaps)) if k not in full),
                key=lambda k: ((times[gaps[k][1]] - times[gaps[k][0]]) / (len(gaps[k][2]) + 1), -k))
        a, b, chosen = gaps[g]
        span = times[b] - times[a]
        want = len(chosen) + 1
        picked = []
        for step in range(1, want + 1):
            target = times[a] + span * step / (want + 1)
            near = [i for i in pool if times[a] < times[i] < times[b] and i not in picked
                    and all(abs(times[i] - times[k]) >= min_gap for k in (a, b, *picked))]
            if not near:
                break
            picked.append(min(near, key=lambda i: (abs(times[i] - target), i)))
        if len(picked) < want:
            full.add(g)
            continue
        gaps[g][2] = picked
        total += 1
    return set(anchors).union(*(set(c) for _, _, c in gaps))


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
    # "30/30 · 60.000s · before switch" in a monospace font, with room
    label_w = math.ceil(LABEL_PX * 0.62 * (len(tile_label(MAX_TILES, MAX_TILES, 60, True)) + 1))

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


def _clean(folder):
    stem, ext = os.path.splitext(SHEET)
    for name in os.listdir(folder):
        if name in (GIF, SHEET, _PALETTE) or (name.startswith(stem + "-") and name.endswith(ext)):
            os.remove(os.path.join(folder, name))
    shutil.rmtree(os.path.join(folder, FRAMES), ignore_errors=True)


def process(folder, scale=1, colors=None):
    """Turn folder/raw.mkv, recorded on an output of this scale, into the
    GIF, the sheets' frames and the sheets, then delete raw.mkv. Returns
    {"distinct": n, "frames": [(name, time)], "sheets": [path]}. Raises
    ProcessError; raw.mkv is kept then."""
    folder = os.path.abspath(folder)  # ffmpeg runs elsewhere for the change listing
    raw = os.path.join(folder, RAW)
    if not os.path.isfile(raw):
        raise ProcessError(f"{raw} is missing")
    colors = colors or theme.colors()
    _clean(folder)
    t0, end = _span(raw)

    # 1: palette for the GIF, the frames that differ for the sheets, and how
    # much of the frame changes at each frame (where the screen switched)
    with tempfile.TemporaryDirectory() as tmp:
        listing = _ffmpeg(["-i", raw, "-filter_complex",
                           f"[0:v]split=3[a][b][c];[a]{EXACT},palettegen=stats_mode=diff[p];"
                           f"[b]{SIMILAR}[s];[c]{CHANGES_FILTER}[d]",
                           "-map", "[p]", *_BITEXACT, "-frames:v", "1", "-update", "1",
                           os.path.join(folder, _PALETTE),
                           "-map", "[s]", "-fps_mode", "passthrough", "-f", "framemd5", "-",
                           "-map", "[d]", "-fps_mode", "passthrough", "-f", "null", "-"],
                          "reading the recording", cwd=tmp)
        changes = [(t - t0, a) for t, a in _read_changes(os.path.join(tmp, _CHANGES))]
    times = [t - t0 for t in _framemd5_times(listing)]
    if not times:
        raise ProcessError("the recording has no frames")
    cuts = switches(changes)
    kept = pick(times, cuts)
    before = _around(times, cuts)[0]

    # 2: the GIF, and the sheets' frames
    frames = os.path.join(folder, FRAMES)
    os.makedirs(frames)
    select = "+".join(f"eq(n,{i})" for i in kept)
    _ffmpeg(["-i", raw, "-i", os.path.join(folder, _PALETTE), "-filter_complex",
             f"[0:v]split[a][b];[a]{EXACT}[g];"
             f"[g][1:v]paletteuse=dither={DITHER}:diff_mode=rectangle[gif];"
             f"[b]{SIMILAR},select='{select}'[f]",
             "-map", "[gif]", "-fps_mode", "passthrough", "-loop", "0", *_BITEXACT,
             os.path.join(folder, GIF),
             "-map", "[f]", "-fps_mode", "passthrough", *_BITEXACT, "-start_number", "1",
             os.path.join(frames, "%04d.png")],
            "writing the GIF")
    set_duration(os.path.join(folder, GIF), end - t0)
    names, tiles = [], []
    for n, i in enumerate(kept, 1):
        name = frame_name(n, times[i])
        os.rename(os.path.join(frames, f"{n:04d}.png"), os.path.join(frames, name))
        names.append((name, times[i]))
        tiles.append((name, tile_label(n, len(kept), times[i], i in before)))

    # 3: the sheets
    w, h = _size(os.path.join(frames, names[0][0]))
    counts = split(len(names), w, h, min(1.0, MIN_TEXT_SCALE / scale))
    sheets, first = [], 0
    for name, count in zip(sheet_names(len(counts)), counts):
        sheets.append(os.path.join(folder, name))
        sheet(frames, tiles[first:first + count], (w, h), sheets[-1], colors)
        first += count
    os.remove(os.path.join(folder, _PALETTE))
    os.remove(raw)
    return {"distinct": len(times), "frames": [(n, float(t)) for n, t in names],
            "sheets": sheets}


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
