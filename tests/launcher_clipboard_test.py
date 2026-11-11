#!/usr/bin/env python3
"""Tests for the launcher's dmenu row options and launcher-clipboard's sorting
(widgets/launcher/options.py, clipboard.py). No GTK, no cliphist: entries
come from a fake listing, decode() from a dict, files from a temp dir.

  python3 tests/launcher_clipboard_test.py
"""

import os
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


if __name__ == "__main__":
    unittest.main(verbosity=1)
