"""Webcam backgrounds: link files played through yt-dlp, a link added from
the popup, and the background grid. yt-dlp is a stand-in script on PATH
that serves a local clip, so no test reaches the network."""

import os
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from gtk_widgets.lib.ui.widget_base import Gtk
from gtk_widgets.widgets.webcam import links
from gtk_widgets.widgets.webcam.effects import Animation
from gtk_widgets.widgets.webcam.gallery import REMOVE_GLYPH, Gallery

LINK = "https://example.com/video"
WAIT_S = 10  # each wait below takes ~1-3 s when the code is right


def _wait_for(done: Callable[[], bool]) -> bool:
    deadline = time.monotonic() + WAIT_S
    while not done():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


def _script(path: Path, body: str) -> None:
    _ = path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{body}\n")
    path.chmod(0o755)


@pytest.fixture
def clip(tmp_path: Path) -> Path:
    """A 1 s video, streamable from a pipe."""
    path = tmp_path / "clip.mp4"
    _ = subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=30:duration=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture
def yt_dlp_serving(tmp_path: Path, clip: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A yt-dlp on PATH that writes the clip to stdout; returns the file
    each run appends a line to."""
    runs = tmp_path / "runs.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _script(bin_dir / "yt-dlp", f"echo run >> '{runs}'\ncat '{clip}'")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    return runs


@pytest.fixture
def no_yt_dlp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PATH with ffmpeg but no yt-dlp."""
    bin_dir = tmp_path / "nobin"
    bin_dir.mkdir()
    for tool in ("ffmpeg", "bash", "cat"):
        found = subprocess.run(
            ["which", tool], capture_output=True, text=True, check=True
        ).stdout.strip()
        (bin_dir / tool).symlink_to(found)
    monkeypatch.setenv("PATH", str(bin_dir))


def _runs(log: Path) -> int:
    return len(log.read_text().split()) if log.exists() else 0


def test_short_link_clip_starts_again_when_it_ends(
    tmp_path: Path, yt_dlp_serving: Path
) -> None:
    link = tmp_path / "clip.url"
    _ = link.write_text(f"{LINK}\n")
    player = Animation(str(link))
    try:
        assert _wait_for(lambda: _runs(yt_dlp_serving) >= 3), (
            f"a 1 s clip played {_runs(yt_dlp_serving)} times in {WAIT_S} s"
        )
    finally:
        player.close()


def test_upper_case_link_file_plays_as_a_link(
    tmp_path: Path, yt_dlp_serving: Path
) -> None:
    link = tmp_path / "Clip.URL"
    _ = link.write_text(f"{LINK}\n")
    player = Animation(str(link))
    try:
        assert _wait_for(lambda: player.latest() is not None)
        assert _runs(yt_dlp_serving) >= 1
    finally:
        player.close()


@pytest.mark.usefixtures("no_yt_dlp")
def test_link_player_keeps_going_without_yt_dlp(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    link = tmp_path / "clip.url"
    _ = link.write_text(f"{LINK}\n")
    player = Animation(str(link))
    try:
        # It says why, and tries again (after LINK_RETRY_S) instead of dying
        said: list[str] = []
        assert _wait_for(
            lambda: (
                said.append(capfd.readouterr().err)
                or "".join(said).count("yt-dlp") >= 2
            )
        ), said
    finally:
        player.close()


@pytest.mark.usefixtures("no_yt_dlp")
def test_adding_a_link_without_yt_dlp_says_so(tmp_path: Path) -> None:
    added = links.add_link(LINK, tmp_path)
    assert isinstance(added, links.LinkError)
    assert "yt-dlp" in str(added)


@pytest.mark.usefixtures("no_yt_dlp")
def test_link_thumbnail_without_yt_dlp_is_none(tmp_path: Path) -> None:
    link = tmp_path / "clip.url"
    _ = link.write_text("https://example.com/no-thumbnail-cached\n")
    assert links.thumbnail(link) is None


def test_adding_a_link_to_a_read_only_folder_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _script(bin_dir / "yt-dlp", "printf 'A Title\\nNA\\n'")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    folder = tmp_path / "backgrounds"
    folder.mkdir()
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        added = links.add_link(LINK, folder)
    finally:
        folder.chmod(stat.S_IRWXU)
    assert isinstance(added, links.LinkError)
    assert not any(folder.iterdir())


def test_clicking_the_chosen_background_again_keeps_it_chosen(
    tmp_path: Path,
) -> None:
    for name in ("a.gif", "b.gif"):
        _ = (tmp_path / name).write_bytes(b"")
    chosen: list[str | None] = [str(tmp_path / "a.gif")]
    gallery = Gallery(
        tmp_path,
        suffixes={".gif"},
        kind="GIFs",
        chosen=lambda: chosen[0],
        choose=lambda path: chosen.__setitem__(0, path),
        show_error=lambda text: print(text, file=sys.stderr),
    )
    buttons = _toggles(gallery.box)
    assert [b.get_active() for b in buttons] == [True, False]
    buttons[0].emit("clicked")
    assert [b.get_active() for b in buttons] == [True, False]
    assert chosen[0] == str(tmp_path / "a.gif")
    buttons[1].emit("clicked")
    assert [b.get_active() for b in buttons] == [False, True]
    assert chosen[0] == str(tmp_path / "b.gif")


def _toggles(widget: Gtk.Widget) -> list[Gtk.ToggleButton]:
    """The grid's tile buttons, in order."""
    found: list[Gtk.ToggleButton] = []
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.ToggleButton):
            found.append(child)
        else:
            found += _toggles(child)
        child = child.get_next_sibling()
    return found


def test_the_cross_removes_a_background_at_once(tmp_path: Path) -> None:
    for name in ("a.gif", "b.gif"):
        _ = (tmp_path / name).write_bytes(b"")
    chosen: list[str | None] = [str(tmp_path / "a.gif")]
    gallery = Gallery(
        tmp_path,
        suffixes={".gif"},
        kind="GIFs",
        chosen=lambda: chosen[0],
        choose=lambda path: chosen.__setitem__(0, path),
        show_error=lambda text: print(text, file=sys.stderr),
    )
    _crosses(gallery.box)[0].emit("clicked")
    assert not (tmp_path / "a.gif").exists()
    assert chosen[0] is None
    assert [b.get_tooltip_text() for b in _toggles(gallery.box)] == ["b.gif"]


def _crosses(widget: Gtk.Widget) -> list[Gtk.Button]:
    """The tiles' remove buttons, in order."""
    found: list[Gtk.Button] = []
    child = widget.get_first_child()
    while child is not None:
        if type(child) is Gtk.Button and child.get_label() == REMOVE_GLYPH:
            found.append(child)
        else:
            found += _crosses(child)
        child = child.get_next_sibling()
    return found
