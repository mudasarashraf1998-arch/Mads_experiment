"""Desktop notifications (optional, via notify-send)."""

from __future__ import annotations

import shutil
import subprocess


def available() -> bool:
    return shutil.which("notify-send") is not None


def notify(title: str, message: str, icon: str = "universal-downloader") -> None:
    if not available():
        return
    try:
        subprocess.run(
            ["notify-send", "-a", "Universal Downloader", "-i", icon, title, message],
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        pass
