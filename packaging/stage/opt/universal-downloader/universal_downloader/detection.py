"""Link source detection.

Mirrors the classification rules of the existing terminal backend
(lib/detect.sh) so the GUI and the CLI agree on every link.
"""

from __future__ import annotations

from .utils import url_host

# host -> source
_SOURCE_HOSTS = {
    "drive.google.com": "gdrive",
    "docs.google.com": "gdrive",
    "drive.usercontent.google.com": "gdrive",
    "googleusercontent.com": "gdrive",
    "mega.nz": "mega",
    "www.mega.nz": "mega",
    "mega.io": "mega",
    "www.mega.io": "mega",
    "mega.co.nz": "mega",
    "www.mega.co.nz": "mega",
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "m.youtube.com": "youtube",
    "music.youtube.com": "youtube",
    "youtu.be": "youtube",
    "www.youtu.be": "youtube",
    "youtube-nocookie.com": "youtube",
    "www.youtube-nocookie.com": "youtube",
}

SOURCE_LABELS = {
    "gdrive": "Google Drive",
    "mega": "MEGA",
    "youtube": "YouTube",
    "direct": "Direct file link",
}

SOURCE_DISPLAY_ORDER = ["youtube", "gdrive", "mega", "direct"]


def detect_source(url: str) -> str:
    """Return one of: gdrive, mega, youtube, direct."""
    host = url_host(url)
    return _SOURCE_HOSTS.get(host, "direct")


def detect_kind(source: str, url: str) -> str:
    """For display only: 'Folder' / 'File' / 'Video' / 'Playlist'."""
    if source == "gdrive":
        if "/folders/" in url or "/folder/" in url or "#folders" in url:
            return "Folder"
        return "File"
    if source == "mega":
        if "/folder/" in url or "#F!" in url:
            return "Folder"
        return "File"
    if source == "youtube":
        if "/playlist" in url or "list=" in url:
            return "Playlist"
        return "Video"
    return "File"


def source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, "Unknown")
