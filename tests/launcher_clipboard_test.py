#!/usr/bin/env python3
"""Tests for the launcher's dmenu row options and launcher-clipboard's sorting
(widgets/launcher/options.py, clipboard.py). No GTK, no cliphist: entries
come from a fake listing, decode() from a dict, files from a temp dir.

  python3 tests/launcher_clipboard_test.py
"""

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "widgets", "launcher"))

import clipboard  # noqa: E402
import options  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
WEBP = b"RIFF\x24\0\0\0WEBPVP8 " + b"\x9d" * 24
# 1x1 GIFs: header + colour table, then per frame a control extension and an image
_GIF_HEAD = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
_GIF_FRAME = b"!\xf9\x04\x00\x0a\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00"
GIF_STILL = _GIF_HEAD + _GIF_FRAME + b";"
GIF_ANIM = _GIF_HEAD + _GIF_FRAME + _GIF_FRAME + b";"


class Options(unittest.TestCase):
    def test_plain_line_has_no_options(self):
        self.assertEqual(options.split("12\tswaymsg reload"), ("12\tswaymsg reload", {}))

    def test_pairs_after_nul_and_repeated_keys(self):
        text, opts = options.split("3\tsheets\0kind\x1ffiles\x1fpreview\x1f/a.png\x1fpreview\x1f/b.png")
        self.assertEqual(text, "3\tsheets")
        self.assertEqual(opts, {"kind": ["files"], "preview": ["/a.png", "/b.png"]})
        self.assertEqual(options.first(opts, "preview"), "/a.png")
        self.assertEqual(options.first(opts, "icon", "none"), "none")

    def test_gif_frames(self):
        with tempfile.TemporaryDirectory() as d:
            still, anim, png = (os.path.join(d, n) for n in ("s.gif", "a.gif", "p.gif"))
            for path, data in ((still, GIF_STILL), (anim, GIF_ANIM), (png, PNG)):
                with open(path, "wb") as f:
                    f.write(data)
            self.assertFalse(options.gif_animated(still))
            self.assertTrue(options.gif_animated(anim))
            self.assertFalse(options.gif_animated(png))  # not a GIF
            self.assertFalse(options.gif_animated(os.path.join(d, "gone.gif")))


class Clipboard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.cache = os.path.join(self.dir, "cache")
        self.blobs = {}
        self.decoded = []

    def tearDown(self):
        self.tmp.cleanup()

    def file(self, name, data=b"x"):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def decode(self, cid):
        self.decoded.append(cid)
        return self.blobs[cid]

    def rows(self, *entries):
        """entries: (id, preview text); -> {id: (text, options)}"""
        listing = "\n".join(f"{cid}\t{text}" for cid, text in entries).encode()
        out = clipboard.run(listing, self.decode, root=self.cache)
        return {o.split("\t", 1)[0]: options.split(o.split("\t", 1)[1]) for o in out}

    def test_image_data_is_decoded_once_and_named(self):
        self.blobs["7"] = PNG
        row = self.rows(("7", "[[ binary data 245 KiB png 1920x1080 ]]"))["7"]
        self.assertEqual(row[0], "PNG image · 1920×1080")
        self.assertEqual(row[1]["kind"], ["image"])
        self.assertEqual(row[1]["detail"], ["245 KiB"])
        data = row[1]["preview"][0]
        with open(data, "rb") as f:
            self.assertEqual(f.read(), PNG)
        self.assertEqual(row[1]["icon"], [data])
        self.rows(("7", "[[ binary data 245 KiB png 1920x1080 ]]"))
        self.assertEqual(self.decoded, ["7"])  # the second run reads the cache

    def test_gif_data(self):
        self.blobs["8"] = GIF_ANIM
        row = self.rows(("8", "[[ binary data 1.2 MiB gif 480x270 ]]"))["8"]
        self.assertEqual(row[1]["kind"], ["gif"])

    def test_bytes_cliphist_cannot_name(self):
        self.blobs["5"] = WEBP
        self.blobs["6"] = b"\x8f\x01junk\x00\xff" * 40
        rows = self.rows(("5", "RIFF�� WEBPVP8 �"), ("6", "��junk"))
        self.assertEqual(rows["5"][0], "WEBP image")
        self.assertEqual(rows["5"][1]["kind"], ["image"])
        self.assertTrue(rows["5"][1]["icon"][0].endswith("5.webp"))
        self.assertEqual(rows["6"][0], "Binary data · 320 B")
        self.assertEqual(rows["6"][1]["kind"], ["binary"])
        self.assertNotIn("icon", rows["6"][1])

    def test_file_links(self):
        shot = self.file("shots/screenshot 1.png", PNG)
        rec = self.file("rec/recording.gif", GIF_ANIM)
        pdf = self.file("docs/report.pdf")
        uri = "file://" + shot.replace(" ", "%20")
        rows = self.rows(("1", uri), ("2", "file://" + rec), ("3", "file://" + pdf),
                         ("4", "file:///nowhere/gone.png"))
        self.assertEqual(rows["1"][0], "screenshot 1.png")
        self.assertEqual(rows["1"][1]["kind"], ["image"])
        self.assertEqual(rows["1"][1]["icon"], [shot])
        self.assertEqual(rows["2"][1]["kind"], ["gif"])
        self.assertEqual(rows["3"][1]["kind"], ["file"])
        self.assertNotIn("icon", rows["3"][1])
        self.assertEqual(rows["4"][1]["kind"], ["missing"])
        self.assertTrue(rows["4"][1]["detail"][0].endswith("· missing"))
        self.assertEqual(self.decoded, [])  # whole previews need no decode

    def test_several_links_cut_by_cliphist_are_decoded(self):
        sheets = [self.file(f"rec/sheet-{i}.png", PNG) for i in (1, 2, 3)]
        self.blobs["9"] = "\r\n".join("file://" + s for s in sheets).encode()
        row = self.rows(("9", "file://" + sheets[0] + " file://" + sheets[1][:20] + "…"))["9"]
        self.assertEqual(row[1]["kind"], ["files"])
        self.assertEqual(row[1]["preview"], sheets)
        self.assertEqual(row[1]["count"], ["3"])
        self.assertEqual(row[1]["icon"], [sheets[0]])
        self.assertTrue(row[0].startswith("3 files: sheet-1.png, sheet-2.png"))

    def test_plain_paths_and_text(self):
        folder = os.path.join(self.dir, "forks", "tmux")
        os.makedirs(folder)
        self.blobs.update({"2": b"/no/such/path", "3": b"git log --oneline -20"})
        rows = self.rows(("1", folder), ("2", "/no/such/path"), ("3", "git log --oneline -20"))
        self.assertEqual(rows["1"][0], "tmux/")
        self.assertEqual(rows["1"][1]["kind"], ["folder"])
        self.assertEqual(rows["2"][1]["kind"], ["text"])  # not a file: left as typed
        self.assertEqual(rows["3"][0], "git log --oneline -20")
        self.assertEqual(rows["3"][1]["kind"], ["text"])

    def test_text_keeps_its_lines_privately(self):
        # cliphist's preview joins lines and cuts at 100 characters; the pane gets the whole text
        full = "def f():\n    return 1\n\n\tdone\n" + "x" * 300
        self.blobs["5"] = full.encode()
        row = self.rows(("5", "def f(): return 1 done xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx…"))["5"]
        path = row[1]["text"][0]
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), full)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.cache).st_mode & 0o777, 0o700)
        self.rows(("5", "def f(): return 1 done"))
        self.assertEqual(self.decoded, ["5"])  # decoded once

    def test_cache_keeps_only_listed_entries(self):
        self.blobs.update({"1": PNG, "2": PNG})
        self.rows(("1", "[[ binary data 1 KiB png 1x1 ]]"), ("2", "[[ binary data 1 KiB png 1x1 ]]"))
        self.rows(("2", "[[ binary data 1 KiB png 1x1 ]]"))
        self.assertEqual(sorted(os.listdir(self.cache)), ["2.png"])

    def test_pick_still_decodes(self):
        # cliphist decode reads only "<id>\t": the options after the label must not change that
        self.blobs["4"] = PNG
        out = clipboard.run(b"4\t[[ binary data 1 KiB png 1x1 ]]", self.decode, root=self.cache)
        self.assertTrue(out[0].startswith("4\t"))
        self.assertNotIn("\n", out[0])


class FakeCliphist:
    """cliphist over a list of (id, list text, bytes), newest first; store
    moves identical bytes to the top under a new id, as cliphist does."""

    def __init__(self, entries):
        self.entries = list(entries)
        self.next = max(int(e[0]) for e in entries) + 1

    def __call__(self, *args, data=None):
        if args == ("list",):
            return b"\n".join(f"{i}\t{t}".encode() for i, t, _ in self.entries) + b"\n"
        if args == ("decode",):
            cid = data.decode().split("\t")[0]
            return next(r for i, _, r in self.entries if i == cid)
        if args == ("store",):
            old = next(e for e in self.entries if e[2] == data)
            self.entries.remove(old)
            self.entries.insert(0, (str(self.next), old[1], data))
            self.next += 1
            return b""
        raise AssertionError(args)


class Restore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "cache")
        self.served, self.copied = [], []

    def tearDown(self):
        self.tmp.cleanup()

    def restore(self, cliphist, cid):
        clipboard.restore(cid, cliphist, self.served.append, self.copied.append, self.root)

    def types(self):
        return [m for m, _ in self.served[0]]

    def test_image_data_goes_up_as_bytes_file_and_path(self):
        ch = FakeCliphist([("7", "hello", b"hello"),
                           ("5", "[[ binary data 40 B png 1x1 ]]", PNG)])
        self.restore(ch, "5")
        self.assertEqual(ch.entries[0][0], "8")  # moved to the top, new id
        path = os.path.join(self.root, "8.png")
        self.assertEqual(pathlib.Path(path).read_bytes(), PNG)
        forms = dict(self.served[0])
        self.assertEqual(self.types()[0], "image/png")
        self.assertEqual(forms["image/png"], PNG)
        self.assertEqual(forms["text/uri-list"], f"file://{path}".encode())
        self.assertEqual(forms["text/plain"], path.encode())
        self.assertIn(clipboard.MARKER, forms)
        self.assertEqual(self.copied, [])

    def test_cached_file_follows_the_new_id(self):
        os.makedirs(self.root)
        with open(os.path.join(self.root, "5.png"), "wb") as f:
            f.write(PNG)
        ch = FakeCliphist([("5", "[[ binary data 40 B png 1x1 ]]", PNG)])
        self.restore(ch, "5")
        self.assertEqual(sorted(os.listdir(self.root)), ["6.png"])

    def test_sniffed_webp_is_image_data(self):
        ch = FakeCliphist([("3", "RIFF\ufffd", WEBP)])
        self.restore(ch, "3")
        self.assertEqual(self.types()[0], "image/webp")

    def test_gif_link_goes_as_file_and_path_never_bytes(self):
        gif = os.path.join(self.tmp.name, "rec ording.gif")
        with open(gif, "wb") as f:
            f.write(GIF_ANIM)
        uri = pathlib.Path(gif).as_uri().encode()
        ch = FakeCliphist([("4", uri.decode(), uri)])
        self.restore(ch, "4")
        forms = dict(self.served[0])
        self.assertEqual(self.types()[0], "text/uri-list")
        self.assertEqual(forms["text/uri-list"], uri)
        self.assertEqual(forms["text/plain;charset=utf-8"], gif.encode())
        self.assertNotIn("image/gif", forms)

    def test_still_image_link_also_offers_bytes(self):
        png = os.path.join(self.tmp.name, "shot.png")
        with open(png, "wb") as f:
            f.write(PNG)
        uri = pathlib.Path(png).as_uri().encode()
        self.restore(FakeCliphist([("4", uri.decode(), uri)]), "4")
        self.assertEqual(dict(self.served[0])["image/png"], PNG)

    def test_several_links_give_paths_one_per_line(self):
        a, b = (os.path.join(self.tmp.name, n) for n in ("sheet-1.png", "sheet-2.png"))
        raw = f"file://{a}\r\nfile://{b}".encode()
        self.restore(FakeCliphist([("9", raw.decode(), raw)]), "9")
        forms = dict(self.served[0])
        self.assertEqual(forms["text/plain"], f"{a}\n{b}".encode())
        self.assertNotIn("image/png", forms)

    def test_text_goes_through_wl_copy(self):
        ch = FakeCliphist([("2", "/etc/hostname", b"/etc/hostname"), ("1", "hi", b"hi")])
        self.restore(ch, "2")
        self.restore(ch, "1")
        self.assertEqual(self.copied, [b"/etc/hostname", b"hi"])
        self.assertEqual(self.served, [])

    def test_offer_keeps_the_entry_and_its_id(self):
        ch = FakeCliphist([("5", "[[ binary data 40 B png 1x1 ]]", PNG), ("4", "hi", b"hi")])
        clipboard.restore("5", ch, self.served.append, self.copied.append, self.root, offer=True)
        self.assertEqual([e[0] for e in ch.entries], ["5", "4"])
        self.assertEqual(dict(self.served[0])["text/plain"],
                         os.path.join(self.root, "5.png").encode())

    def test_offer_leaves_text_alone(self):
        ch = FakeCliphist([("4", "hi", b"hi")])
        clipboard.restore("4", ch, self.served.append, self.copied.append, self.root, offer=True)
        self.assertEqual((self.served, self.copied), ([], []))

    def test_failed_serve_falls_back_to_wl_copy(self):
        def broken(forms):
            raise OSError("no data-control")
        ch = FakeCliphist([("5", "[[ binary data 40 B png 1x1 ]]", PNG)])
        clipboard.restore("5", ch, broken, self.copied.append, self.root)
        self.assertEqual(self.copied, [PNG])


if __name__ == "__main__":
    unittest.main(verbosity=1)
