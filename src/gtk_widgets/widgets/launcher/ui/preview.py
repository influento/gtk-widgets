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
from concurrent.futures import ThreadPoolExecutor

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

from gtk_widgets.widgets.launcher import options

THUMB_W, THUMB_H = 64, 46   # logical px; decoded at 2x for scale-2 outputs
THUMB_ROW_H = 56            # a row with a thumbnail; text rows keep the 34 px of style.css
TEXT_MAX = 64 << 10         # the pane shows this much of a text: Pango lays out all of it
ICONS = {"text": "text-x-generic", "folder": "folder", "missing": "image-missing",
         "binary": "application-octet-stream", "file": "text-x-generic"}

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="launcher-preview")


def human(n):
    for unit in ("B", "KiB", "MiB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GiB"


def short(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path == home or path.startswith(home + "/") else path


def image_info(path):
    """(format name, width, height) from the file's header, or None."""
    if not os.path.isfile(path):
        return None
    fmt, w, h = GdkPixbuf.Pixbuf.get_file_info(path)
    return (fmt.get_name(), w, h) if fmt else None


def read_text(path):
    """(text, total bytes) of a text file, cut at TEXT_MAX; None when unreadable."""
    try:
        with open(path, "rb") as f:
            raw = f.read(TEXT_MAX + 1)
            size = os.fstat(f.fileno()).st_size
    except OSError:
        return None
    text = raw[:TEXT_MAX].decode("utf-8", "replace")
    return (text + "\n…" if size > TEXT_MAX else text), size


def fit(w, h, box_w, box_h):
    f = min(box_w / w, box_h / h, 1.0)
    return max(2, int(w * f)), max(2, int(h * f))


def _pixbuf_texture(pb):
    fmt = Gdk.MemoryFormat.R8G8B8A8 if pb.get_has_alpha() else Gdk.MemoryFormat.R8G8B8
    return Gdk.MemoryTexture.new(pb.get_width(), pb.get_height(), fmt,
                                 pb.read_pixel_bytes(), pb.get_rowstride())


def _gif_frame(path, w, h):
    """The first frame of a GIF at w x h, through ffmpeg."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-frames:v", "1",
                        "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgba", "pipe:1"],
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
    if len(r.stdout) != w * h * 4:
        return None
    return Gdk.MemoryTexture.new(w, h, Gdk.MemoryFormat.R8G8B8A8, GLib.Bytes.new(r.stdout), w * 4)


class TextureCache:
    """Textures by (path, mtime, size), newest kept; load() runs on the pool."""

    def __init__(self, size, box=None):
        self.cache = OrderedDict()
        self.size, self.box = size, box

    def key(self, path):
        try:
            return (path, os.stat(path).st_mtime_ns, self.box)
        except OSError:
            return None

    def get(self, key):
        tex = self.cache.get(key)
        if tex is not None:
            self.cache.move_to_end(key)
        return tex

    def put(self, key, tex):
        self.cache[key] = tex
        while len(self.cache) > self.size:
            self.cache.popitem(last=False)

    def _decode(self, path):
        info = image_info(path)
        if info is None:
            return None
        if self.box is None:
            return Gdk.Texture.new_from_filename(path)
        w, h = fit(info[1], info[2], *self.box)
        if info[0] == "gif":
            return _gif_frame(path, w, h)
        return _pixbuf_texture(GdkPixbuf.Pixbuf.new_from_file_at_scale(path, w, h, True))

    def load(self, path, done):
        """done(texture or None) on the main thread; at once when cached."""
        key = self.key(path)
        if key is None:
            done(None)
            return
        tex = self.get(key)
        if tex is not None:
            done(tex)
            return

        def work():
            try:
                tex = self._decode(path)
            except (GLib.Error, OSError, subprocess.SubprocessError):
                tex = None
            GLib.idle_add(finish, tex)

        def finish(tex):
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

    def __init__(self, w, h):
        super().__init__(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
        self.w, self.h = w, h

    def set_box(self, w, h):
        self.w, self.h = w, h
        self.queue_resize()

    def do_measure(self, orientation, _for_size):
        v = self.w if orientation == Gtk.Orientation.HORIZONTAL else self.h
        return v, v, -1, -1


def icon_for(kind, path):
    if path and os.path.isdir(path):
        return Gio.ThemedIcon.new("folder")
    if kind in ("file", "files", "image", "gif") and path and os.path.isfile(path):
        ctype, _ = Gio.content_type_guess(path, None)
        return Gio.content_type_get_icon(ctype)
    if kind in ("files", "image", "gif") and path and not os.path.exists(path):
        return Gio.ThemedIcon.new("image-missing")
    return Gio.ThemedIcon.new(ICONS.get(kind, "text-x-generic"))


class Slot(Gtk.Overlay):
    """A row's thumbnail, or its kind's icon, in a column of THUMB_W."""

    def __init__(self):
        super().__init__(valign=Gtk.Align.CENTER)
        self.set_size_request(THUMB_W, -1)
        box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.pic = FixedPicture(THUMB_W, THUMB_H)
        self.pic.add_css_class("launcher-thumb")
        box.append(self.pic)
        self.icon = Gtk.Image(pixel_size=22)
        box.append(self.icon)
        self.set_child(box)
        self.badge = Gtk.Label(halign=Gtk.Align.END, valign=Gtk.Align.END, visible=False)
        self.badge.add_css_class("launcher-badge")
        self.add_overlay(self.badge)
        self.path = None

    def show(self, opts):
        """Fill from a row's options; True when it shows a thumbnail."""
        kind = options.first(opts, "kind", "text")
        thumb = options.first(opts, "icon")
        self.path = thumb
        pic = kind in options.PIC_KINDS and bool(thumb)
        self.pic.set_visible(pic)
        self.icon.set_visible(not pic)
        if pic:
            self.pic.set_paintable(None)
            THUMBS.load(thumb, lambda tex, p=thumb: self.path == p and self.pic.set_paintable(tex))
        else:
            self.icon.set_from_gicon(icon_for(kind, options.first(opts, "preview")))
        badge = "GIF" if kind == "gif" else options.first(opts, "count")
        self.badge.set_label(badge)
        self.badge.set_visible(bool(badge))
        return pic


class GifPlayer:
    """Plays a GIF through ffmpeg at w x h device pixels, in real time, looping."""

    def __init__(self, on_frame):
        self.on_frame = on_frame
        self.proc = None
        self.watch = 0

    def start(self, path, w, h):
        self.stop()
        self.w, self.h, self.frame = w, h, w * h * 4
        self.buf = bytearray()
        try:
            self.proc = subprocess.Popen(
                ["ffmpeg", "-nostdin", "-v", "error", "-re", "-stream_loop", "-1", "-i", path,
                 "-vf", f"scale={w}:{h}:flags=bicubic", "-f", "rawvideo", "-pix_fmt", "rgba",
                 "pipe:1"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            self.proc = None
            return False
        fd = self.proc.stdout.fileno()
        os.set_blocking(fd, False)
        self.watch = GLib.unix_fd_add_full(GLib.PRIORITY_DEFAULT, fd,
                                           GLib.IOCondition.IN | GLib.IOCondition.HUP, self._read)
        return True

    def _read(self, fd, _cond):
        try:
            chunk = os.read(fd, 1 << 20)
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
            last = bytes(self.buf[:self.frame])
            del self.buf[:self.frame]
        if last is not None:
            self.on_frame(Gdk.MemoryTexture.new(self.w, self.h, Gdk.MemoryFormat.R8G8B8A8,
                                                GLib.Bytes.new(last), self.w * 4))
        return GLib.SOURCE_CONTINUE

    def stop(self):
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

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add_css_class("launcher-pane")
        self.stack = Gtk.Stack()
        self.stack.add_css_class("launcher-pane-view")
        self.picture = FixedPicture(300, 200)
        self.stack.add_named(self.picture, "picture")
        self.icon = Gtk.Image(pixel_size=96)
        self.stack.add_named(self.icon, "icon")
        # max_width_chars=1: long text wraps instead of widening the pane
        self.text = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, xalign=0, yalign=0,
                              max_width_chars=1, margin_top=10, margin_bottom=10,
                              margin_start=12, margin_end=12)
        self.text.add_css_class("launcher-pane-text")
        self.stack.add_named(Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                                child=self.text), "text")
        self.append(self.stack)
        self.caption = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE,
                                 max_width_chars=1, hexpand=True)
        self.caption.add_css_class("launcher-pane-caption")
        self.append(self.caption)
        self.meta = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE,
                              max_width_chars=1, hexpand=True)
        self.meta.add_css_class("launcher-pane-meta")
        self.append(self.meta)
        self.player = GifPlayer(self.picture.set_paintable)
        self.item, self.page_i, self.gen = None, 0, 0
        self.view_w = self.view_h = 1

    def set_view_size(self, w, h):
        self.view_w, self.view_h = w, h
        self.stack.set_size_request(w, h)
        self.picture.set_box(w, h)

    def show_item(self, item):
        self.item, self.page_i = item, 0
        self._render()

    def page(self, delta):
        files = self._files()
        if len(files) > 1:
            self.page_i = (self.page_i + delta) % len(files)
            self._render()

    def stop(self):
        self.player.stop()
        self.gen += 1  # a load still on the pool lands nowhere

    def _files(self):
        return self.item.opts.get("preview", []) if self.item is not None else []

    def _render(self):
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
            self.text.get_parent().get_vadjustment().set_value(0)  # a new text starts at its top
            lines = text.count("\n") + (not text.endswith("\n"))
            self.caption.set_text("Text")
            self.meta.set_text(f"{lines} line{'s' * (lines != 1)} · {human(size)}"
                               + (f" · first {human(TEXT_MAX)} shown" if size > TEXT_MAX else ""))
            return
        path = files[self.page_i]
        data = options.first(item.opts, "info") == "image data"
        name = item.text if data else os.path.basename(path.rstrip("/")) or path
        pos = f"   {self.page_i + 1} of {len(files)} · Ctrl+←/→" if len(files) > 1 else ""
        self.caption.set_text(name + pos)
        info = image_info(path)
        self.meta.set_text(self._meta(path, info, data))
        if info is None:
            self.icon.set_from_gicon(icon_for(kind, path))
            self.stack.set_visible_child_name("icon")
            return
        self.picture.set_paintable(None)
        self.stack.set_visible_child_name("picture")
        if info[0] == "gif" and options.gif_animated(path):
            scale = self.get_scale_factor()
            if self.player.start(path, *fit(info[1], info[2], self.view_w * scale,
                                            self.view_h * scale)):
                return
        gen = self.gen
        FULL.load(path, lambda tex: gen == self.gen and self.picture.set_paintable(tex))

    @staticmethod
    def _meta(path, info, data):
        if not os.path.exists(path):
            return f"missing · {short(os.path.dirname(path))}"
        if os.path.isdir(path):
            return f"folder · {short(path)}"
        if info is not None:
            kind = f"{info[0].upper()} {info[1]}×{info[2]}"
        else:
            kind = Gio.content_type_get_description(Gio.content_type_guess(path, None)[0])
        where = "image data" if data else short(os.path.dirname(path))
        return f"{kind} · {human(os.path.getsize(path))} · {where}"
