"""Backgrounds from a link: a `.url` file in the backgrounds folder holds a
YouTube (or any yt-dlp site) link on its first line. yt-dlp downloads the
video for ffmpeg to play, and gives its title and thumbnail for the popup (stdlib:
the engine and the popup both use it)."""

import contextlib
import hashlib
import subprocess
from pathlib import Path

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.widgets.webcam.parse import (
    LinkInfo,
    parse_link,
    parse_link_info,
    parse_url_line,
)

LINK_SUFFIX = ".url"
# Video only (one URL, no merge), H.264 first (the cheapest to decode), at
# most 720p and 30 fps: the engine scales to 720p and keeps 30 fps anyway
STREAM_FORMAT = (
    "bv*[height<=720][fps<=30][vcodec^=avc1]/bv*[height<=720][vcodec^=avc1]"
    "/bv*[height<=720]/b[height<=720]/bv*/b"
)
RESOLVE_TIMEOUT_S = 60
THUMBNAILS_DIR = Path.home() / ".cache/gtk-widgets/webcam/thumbnails"
THUMBNAIL_WIDTH = 384  # the popup shows it at 96 logical px
FILE_NAME_CHARS = 60


def is_link(path: Path) -> bool:
    return path.suffix.lower() == LINK_SUFFIX


def load_link(path: Path) -> str | ParseError:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return ParseError(f"{path}: {e.strerror}")
    match parse_link(text):
        case ParseError() as e:
            return ParseError(f"{path}: {e}")
        case link:
            return link


def download_argv(link: str) -> list[str]:
    """yt-dlp writing the video to stdout, for ffmpeg to read."""
    return [
        "yt-dlp",
        "--quiet",
        "--no-warnings",
        "--no-playlist",
        "--format",
        STREAM_FORMAT,
        "--output",
        "-",
        link,
    ]


def url_line(output: bytes) -> str | ParseError:
    return parse_url_line(output.decode(errors="replace"))


class LinkError(ValueError):
    """A pasted link that is not one yt-dlp can play."""


def add_link(text: str, folder: Path) -> Path | LinkError:
    """Check a pasted link with yt-dlp and save it as `<title>.url` in
    `folder` (the link's file when it is there already), its thumbnail
    cached. Blocks for seconds."""
    match parse_link(text):
        case ParseError() as e:
            return LinkError(str(e))
        case link:
            pass
    if folder.is_dir():
        for path in sorted(p for p in folder.iterdir() if is_link(p)):
            if load_link(path) == link:
                return path
    match _yt_dlp(["--print", "title", "--print", "thumbnail", link]):
        case LinkError() as e:
            return e
        case found:
            pass
    match parse_link_info(found.decode(errors="replace")):
        case ParseError():
            return LinkError("not a video yt-dlp can play (or no network)")
        case LinkInfo() as info:
            pass
    path = _free_name(folder, info.title)
    tmp = path.with_name(f".{path.name}.part")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        _ = tmp.write_text(f"{link}\n", encoding="utf-8")
        _ = tmp.replace(path)
    except OSError as e:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        return LinkError(f"{folder}: {e.strerror}")
    if info.thumbnail is not None:
        _ = _cache_thumbnail(link, info.thumbnail)
    return path


def _free_name(folder: Path, title: str) -> Path:
    """`<title>.url` with only safe characters, numbered if taken."""
    safe = "".join(c if c.isalnum() or c in " -_" else " " for c in title)
    stem = " ".join(safe.split())[:FILE_NAME_CHARS].strip() or "video"
    path, n = folder / f"{stem}{LINK_SUFFIX}", 1
    while path.exists():
        n += 1
        path = folder / f"{stem} {n}{LINK_SUFFIX}"
    return path


def _yt_dlp(args: list[str]) -> bytes | LinkError:
    """yt-dlp's output (empty when it fails); LinkError when it cannot run
    or times out."""
    try:
        done = subprocess.run(
            [
                "yt-dlp",
                "--quiet",
                "--no-warnings",
                "--no-playlist",
                "--skip-download",
                *args,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=RESOLVE_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return LinkError("yt-dlp took too long (no network?)")
    except OSError as e:
        return LinkError(f"yt-dlp: {e.strerror} (is yt-dlp installed?)")
    return done.stdout


def forget(path: Path) -> None:
    """Delete a link file's cached thumbnail (before the file goes)."""
    match load_link(path):
        case ParseError():
            pass
        case link:
            _cached(link).unlink(missing_ok=True)


def _cached(link: str) -> Path:
    name = hashlib.sha256(link.encode()).hexdigest()[:16]
    return THUMBNAILS_DIR / f"{name}.png"


def thumbnail(path: Path) -> Path | None:
    """The link's thumbnail image, downloaded once into THUMBNAILS_DIR;
    None when the link or the network fails. Blocks for seconds."""
    match load_link(path):
        case ParseError():
            return None
        case link:
            pass
    if (cached := _cached(link)).exists():
        return cached
    match _yt_dlp(["--print", "thumbnail", link]):
        case LinkError():
            return None
        case found:
            pass
    match url_line(found):
        case ParseError():
            return None
        case url:
            return _cache_thumbnail(link, url)


def _cache_thumbnail(link: str, url: str) -> Path | None:
    cached = _cached(link)
    tmp = cached.with_suffix(".part.png")
    try:
        THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
        done = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                url,
                "-vf",
                f"scale={THUMBNAIL_WIDTH}:-2",
                "-frames:v",
                "1",
                str(tmp),
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=RESOLVE_TIMEOUT_S,
            check=False,
        )
        if done.returncode != 0:
            tmp.unlink(missing_ok=True)
            return None
        _ = tmp.replace(cached)
    except subprocess.TimeoutExpired, OSError:  # the cache is not writable
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        return None
    return cached
