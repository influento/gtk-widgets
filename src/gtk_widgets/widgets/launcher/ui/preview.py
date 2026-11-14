"""Row thumbnails and the preview pane for dmenu rows with options (options.py).

Images are decoded on worker threads and cached by path and mtime in the
resident instance, so only the first show of an image pays for it. A GIF
never goes through GdkPixbuf (it would decode every frame at once): ffmpeg
gives the thumbnail's first frame, and plays the selected one in the pane
at the pane's pixel size, one frame in memory at a time.
"""

import os
import subprocess
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Protocol, override

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

from gtk_widgets.lib.ui.widget_base import Orientation
from gtk_widgets.widgets.launcher import options
from gtk_widgets.widgets.launcher.options import Options, human, name_of, parent, short

THUMB_W, THUMB_H = 64, 46  # logical px; decoded at 2x for scale-2 outputs
THUMB_ROW_H = 56  # a row with a thumbnail; text rows keep the 34 px of style.css
TEXT_MAX = 64 << 10  # the pane shows this much of a text: Pango lays out all of it
FFMPEG_TIMEOUT_S = 10
RGBA = 4  # bytes per pixel
READ_BYTES = 1 << 20
ICONS = {
    "text": "text-x-generic",
    "folder": "folder",
    "missing": "image-missing",
    "binary": "application-octet-stream",
    "file": "text-x-generic",
}

type ImageInfo = tuple[str, int, int]  # (format name, width, height)
# (path, mtime in ns, decode box): a changed file is a new key
type TextureKey = tuple[str, int, tuple[int, int] | None]

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="launcher-preview")


class Shown(Protocol):
    """What the pane shows of a row."""

    text: str
    opts: Options


def image_info(path: str) -> ImageInfo | None:
    """(format name, width, height) from the file's header, or None."""
    if not Path(path).is_file():
        return None
    fmt, w, h = GdkPixbuf.Pixbuf.get_file_info(path)
    name = fmt.get_name() if fmt is not None else None
    return (name, w, h) if name is not None else None


def read_text(path: str) -> tuple[str, int] | None:
    """(text, total bytes) of a text file, cut at TEXT_MAX; None when unreadable."""
    try:
        with Path(path).open("rb") as f:
            raw = f.read(TEXT_MAX + 1)
            size = os.fstat(f.fileno()).st_size
    except OSError:
        return None
    text = raw[:TEXT_MAX].decode("utf-8", "replace")
    return (text + "\n…" if size > TEXT_MAX else text), size


def fit(w: int, h: int, box_w: int, box_h: int) -> tuple[int, int]:
    f = min(box_w / w, box_h / h, 1.0)
    return max(2, int(w * f)), max(2, int(h * f))


def _pixbuf_texture(pb: GdkPixbuf.Pixbuf) -> Gdk.Texture:
    fmt = Gdk.MemoryFormat.R8G8B8A8 if pb.get_has_alpha() else Gdk.MemoryFormat.R8G8B8
    return Gdk.MemoryTexture.new(
        pb.get_width(), pb.get_height(), fmt, pb.read_pixel_bytes(), pb.get_rowstride()
    )


def _gif_frame(path: str, w: int, h: int) -> Gdk.Texture | None:
    """The first frame of a GIF at w x h, through ffmpeg."""
    r = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            path,
            "-frames:v",
            "1",
            "-vf",
            f"scale={w}:{h}",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "pipe:1",
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=FFMPEG_TIMEOUT_S,
        check=False,
    )
    if len(r.stdout) != w * h * RGBA:
        return None
    return Gdk.MemoryTexture.new(
        w, h, Gdk.MemoryFormat.R8G8B8A8, GLib.Bytes.new(r.stdout), w * RGBA
    )


class TextureCache:
    """Textures by (path, mtime, size), newest kept; load() runs on the pool."""

    def __init__(self, size: int, box: tuple[int, int] | None = None) -> None:
        self.cache: OrderedDict[TextureKey, Gdk.Texture] = OrderedDict()
        self.size, self.box = size, box

    def key(self, path: str) -> TextureKey | None:
        try:
            return (path, Path(path).stat().st_mtime_ns, self.box)
        except OSError:
            return None

    def get(self, key: TextureKey) -> Gdk.Texture | None:
        tex = self.cache.get(key)
        if tex is not None:
            self.cache.move_to_end(key)
        return tex

    def put(self, key: TextureKey, tex: Gdk.Texture) -> None:
        self.cache[key] = tex
        while len(self.cache) > self.size:
            self.cache.popitem(last=False)

    def _decode(self, path: str) -> Gdk.Texture | None:
        info = image_info(path)
        if info is None:
            return None
        if self.box is None:
            return Gdk.Texture.new_from_filename(path)
        w, h = fit(info[1], info[2], *self.box)
        if info[0] == "gif":
            return _gif_frame(path, w, h)
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            path, w, h, preserve_aspect_ratio=True
        )
        return _pixbuf_texture(pb) if pb is not None else None

    def load(self, path: str, done: Callable[[Gdk.Texture | None], object]) -> None:
        """done(texture or None) on the main thread; at once when cached."""
        key = self.key(path)
        if key is None:
            done(None)
            return
        tex = self.get(key)
        if tex is not None:
            done(tex)
            return

        def work() -> None:
            try:
                tex = self._decode(path)
            except GLib.Error, OSError, subprocess.SubprocessError:
                tex = None
            GLib.idle_add(finish, tex)

        def finish(tex: Gdk.Texture | None) -> bool:
            if tex is not None:
                self.put(key, tex)
            done(tex)
            return GLib.SOURCE_REMOVE

        _pool.submit(work)


THUMBS = TextureCache(300, box=(THUMB_W * 2, THUMB_H * 2))
FULL = TextureCache(6)


class FixedPicture(Gtk.Picture):
    """A picture that asks for a set size, not its image's pixel size (a
    Gtk.Picture's natural size is the texture's, which widens the popup)."""

    def __init__(self, w: int, h: int) -> None:
        super().__init__(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
        self.w, self.h = w, h

    def set_box(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.queue_resize()

    @override
    def do_measure(
        self, orientation: Orientation, for_size: int
    ) -> tuple[int, int, int, int]:
        v = self.w if orientation == Gtk.Orientation.HORIZONTAL else self.h
        return v, v, -1, -1


def icon_for(kind: str, path: str) -> Gio.Icon:
    if path and Path(path).is_dir():
        return Gio.ThemedIcon.new("folder")
    if kind in ("file", "files", "image", "gif") and path and Path(path).is_file():
        ctype, _ = Gio.content_type_guess(path, None)
        return Gio.content_type_get_icon(ctype)
    if kind in ("files", "image", "gif") and path and not Path(path).exists():
        return Gio.ThemedIcon.new("image-missing")
    return Gio.ThemedIcon.new(ICONS.get(kind, "text-x-generic"))


class Slot(Gtk.Overlay):
    """A row's thumbnail, or its kind's icon, in a column of THUMB_W."""

    def __init__(self) -> None:
        super().__init__(valign=Gtk.Align.CENTER)
        self.set_size_request(THUMB_W, -1)
        box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.pic = FixedPicture(THUMB_W, THUMB_H)
        self.pic.add_css_class("launcher-thumb")
        box.append(self.pic)
        self.icon = Gtk.Image(pixel_size=22)
        box.append(self.icon)
        self.set_child(box)
        self.badge = Gtk.Label(
            halign=Gtk.Align.END, valign=Gtk.Align.END, visible=False
        )
        self.badge.add_css_class("launcher-badge")
        self.add_overlay(self.badge)
        self.path = ""

    def fill(self, opts: Options) -> bool:
        """Fill from a row's options; True when it shows a thumbnail."""
        kind = options.first(opts, "kind", "text")
        thumb = options.first(opts, "icon")
        self.path = thumb
        pic = kind in options.PIC_KINDS and bool(thumb)
        self.pic.set_visible(pic)
        self.icon.set_visible(not pic)
        if pic:
            self.pic.set_paintable(None)

            def loaded(tex: Gdk.Texture | None) -> None:
                if self.path == thumb:  # the row may show another line by now
                    self.pic.set_paintable(tex)

            THUMBS.load(thumb, loaded)
        else:
            self.icon.set_from_gicon(icon_for(kind, options.first(opts, "preview")))
        badge = "GIF" if kind == "gif" else options.first(opts, "count")
        self.badge.set_label(badge)
        self.badge.set_visible(bool(badge))
        return pic


class GifPlayer:
    """Plays a GIF through ffmpeg at w x h device pixels, in real time, looping."""

    def __init__(self, on_frame: Callable[[Gdk.Texture], None]) -> None:
        self.on_frame = on_frame
        self.proc: subprocess.Popen[bytes] | None = None
        self.watch = 0
        self.w = self.h = self.frame = 0  # frame: bytes per frame
        self.buf = bytearray()

    def start(self, path: str, w: int, h: int) -> bool:
        self.stop()
        self.w, self.h, self.frame = w, h, w * h * RGBA
        self.buf = bytearray()
        try:
            proc = subprocess.Popen(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-re",
                    "-stream_loop",
                    "-1",
                    "-i",
                    path,
                    "-vf",
                    f"scale={w}:{h}:flags=bicubic",
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "rgba",
                    "pipe:1",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            return False
        self.proc = proc
        if proc.stdout is None:  # never: stdout is a pipe
            return False
        fd = proc.stdout.fileno()
        os.set_blocking(fd, False)
        self.watch = GLib.unix_fd_add_full(
            GLib.PRIORITY_DEFAULT,
            fd,
            GLib.IOCondition.IN | GLib.IOCondition.HUP,
            lambda fd, _cond: self._read(fd),
        )
        return True

    def _read(self, fd: int) -> bool:
        try:
            chunk = os.read(fd, READ_BYTES)
        except BlockingIOError:
            return GLib.SOURCE_CONTINUE
        except OSError:
            chunk = b""
        if not chunk:
            self.watch = 0
            return GLib.SOURCE_REMOVE
        self.buf += chunk
        last = None
        while len(self.buf) >= self.frame:  # behind: show only the newest frame
            last = bytes(self.buf[: self.frame])
            del self.buf[: self.frame]
        if last is not None:
            self.on_frame(
                Gdk.MemoryTexture.new(
                    self.w,
                    self.h,
                    Gdk.MemoryFormat.R8G8B8A8,
                    GLib.Bytes.new(last),
                    self.w * RGBA,
                )
            )
        return GLib.SOURCE_CONTINUE

    def stop(self) -> None:
        if self.watch:
            GLib.source_remove(self.watch)
            self.watch = 0
        if self.proc is not None:
            self.proc.kill()
            self.proc.wait()
            self.proc = None


class Pane(Gtk.Box):
    """The selected row large: an image, a playing GIF, one file of several
    (page()), a file type's icon, or the row's text."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add_css_class("launcher-pane")
        self.stack = Gtk.Stack()
        self.stack.add_css_class("launcher-pane-view")
        self.picture = FixedPicture(300, 200)
        self.stack.add_named(self.picture, "picture")
        self.icon = Gtk.Image(pixel_size=96)
        self.stack.add_named(self.icon, "icon")
        # max_width_chars=1: long text wraps instead of widening the pane
        self.text = Gtk.Label(
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            xalign=0,
            yalign=0,
            max_width_chars=1,
            margin_top=10,
            margin_bottom=10,
            margin_start=12,
            margin_end=12,
        )
        self.text.add_css_class("launcher-pane-text")
        self.text_scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER, child=self.text
        )
        self.stack.add_named(self.text_scroller, "text")
        self.append(self.stack)
        self.caption = Gtk.Label(
            xalign=0,
            ellipsize=Pango.EllipsizeMode.MIDDLE,
            max_width_chars=1,
            hexpand=True,
        )
        self.caption.add_css_class("launcher-pane-caption")
        self.append(self.caption)
        self.meta = Gtk.Label(
            xalign=0,
            ellipsize=Pango.EllipsizeMode.MIDDLE,
            max_width_chars=1,
            hexpand=True,
        )
        self.meta.add_css_class("launcher-pane-meta")
        self.append(self.meta)
        self.player = GifPlayer(self.picture.set_paintable)
        self.item: Shown | None = None
        self.page_i, self.gen = 0, 0
        self.view_w = self.view_h = 1

    def set_view_size(self, w: int, h: int) -> None:
        self.view_w, self.view_h = w, h
        self.stack.set_size_request(w, h)
        self.picture.set_box(w, h)

    def show_item(self, item: Shown | None) -> None:
        self.item, self.page_i = item, 0
        self._render()

    def page(self, delta: int) -> None:
        files = self._files()
        if len(files) > 1:
            self.page_i = (self.page_i + delta) % len(files)
            self._render()

    def stop(self) -> None:
        self.player.stop()
        self.gen += 1  # a load still on the pool lands nowhere

    def _files(self) -> list[str]:
        return self.item.opts.get("preview", []) if self.item is not None else []

    def _render(self) -> None:
        self.stop()
        item = self.item
        if item is None:
            self.text.set_text("")
            self.stack.set_visible_child_name("text")
            self.caption.set_text("")
            self.meta.set_text("")
            return
        kind = options.first(item.opts, "kind", "text")
        files = self._files()
        if not files:
            self._render_text(item, kind)
            return
        path = files[self.page_i]
        data = options.first(item.opts, "info") == "image data"
        name = item.text if data else name_of(path.rstrip("/")) or path
        pos = (
            f"   {self.page_i + 1} of {len(files)} · Ctrl+←/→" if len(files) > 1 else ""
        )
        self.caption.set_text(name + pos)
        info = image_info(path)
        self.meta.set_text(self._meta(path, info, data=data))
        if info is None:
            self.icon.set_from_gicon(icon_for(kind, path))
            self.stack.set_visible_child_name("icon")
            return
        self.picture.set_paintable(None)
        self.stack.set_visible_child_name("picture")
        if info[0] == "gif" and options.gif_animated(path):
            scale = self.get_scale_factor()
            if self.player.start(
                path, *fit(info[1], info[2], self.view_w * scale, self.view_h * scale)
            ):
                return
        gen = self.gen

        def loaded(tex: Gdk.Texture | None) -> None:
            if gen == self.gen:  # else the pane shows another row by now
                self.picture.set_paintable(tex)

        FULL.load(path, loaded)

    def _render_text(self, item: Shown, kind: str) -> None:
        """A row without files: binary data's icon, or its text."""
        if kind == "binary":
            self.icon.set_from_gicon(icon_for(kind, ""))
            self.stack.set_visible_child_name("icon")
            self.caption.set_text(item.text)
            self.meta.set_text("")
            return
        full = read_text(options.first(item.opts, "text"))
        text, size = full if full is not None else (item.text, len(item.text.encode()))
        self.text.set_text(text)
        self.stack.set_visible_child_name("text")
        self.text_scroller.get_vadjustment().set_value(
            0
        )  # a new text starts at its top
        lines = text.count("\n") + (not text.endswith("\n"))
        self.caption.set_text("Text")
        self.meta.set_text(
            f"{lines} line{'s' * (lines != 1)} · {human(size)}"
            + (f" · first {human(TEXT_MAX)} shown" if size > TEXT_MAX else "")
        )

    @staticmethod
    def _meta(path: str, info: ImageInfo | None, *, data: bool) -> str:
        if not Path(path).exists():
            return f"missing · {short(parent(path))}"
        if Path(path).is_dir():
            return f"folder · {short(path)}"
        if info is not None:
            kind = f"{info[0].upper()} {info[1]}{options.TIMES}{info[2]}"
        else:
            kind = Gio.content_type_get_description(
                Gio.content_type_guess(path, None)[0]
            )
        where = "image data" if data else short(parent(path))
        return f"{kind} · {human(Path(path).stat().st_size)} · {where}"
