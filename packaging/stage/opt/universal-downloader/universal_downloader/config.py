"""Application settings.

Stored as a simple KEY=value text file (same style as the existing terminal
backend's config) in ~/.config/universal-downloader/settings.conf.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import __version__
from .paths import settings_file

DEFAULTS: dict[str, Any] = {
    # Where downloads go.
    "download_dir": str(Path.home() / "Videos"),
    # Concurrency: 1 (safe default for old hardware) or 2 (configurable max).
    "max_concurrent": "1",
    # Retry behaviour.
    "retries": "5",
    "retry_wait": "10",
    # YouTube defaults.
    "yt_mode": "video",          # video | audio
    "yt_quality": "best",        # best | 2160 | 1440 | 1080 | 720 | 480 | 360
    "yt_container": "mkv",       # mp4 | mkv
    "yt_audio": "best",          # best | mp3-320 | mp3-192 | mp3-128
    "yt_playlist": "full",       # single | full
    "yt_numbering": "true",
    "yt_archive": "true",
    # Google Drive.
    "gdrive_cookies": "",
    # Direct links.
    "direct_connections": "4",
    # Misc.
    "notifications": "true",
    "process_priority": "0",     # nice value, 0 = normal
}


class Settings:
    """Thread-friendly, on-disk settings store."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else settings_file()
        self._values: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            for raw in self.path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key in DEFAULTS:
                    self._values[key] = value
        except OSError:
            # Keep defaults if the file cannot be read.
            pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# Universal Downloader settings ({__version__})", ""]
        for key in DEFAULTS:
            lines.append(f"{key}={self._values[key]}")
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def get(self, key: str) -> Any:
        return self._values.get(key, DEFAULTS.get(key))

    def getint(self, key: str) -> int:
        try:
            return int(self._values.get(key, DEFAULTS[key]))
        except (TypeError, ValueError):
            return int(DEFAULTS[key])

    def getbool(self, key: str) -> bool:
        return str(self._values.get(key, DEFAULTS[key])).lower() in ("1", "true", "yes", "on")

    def set(self, key: str, value: Any) -> None:
        if key in DEFAULTS:
            self._values[key] = str(value)

    def items(self):
        return dict(self._values)
