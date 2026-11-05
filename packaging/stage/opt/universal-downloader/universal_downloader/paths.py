"""XDG-conformant filesystem locations for the application.

Personal data lives in the user's home directory, never inside /opt.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value else default


def config_dir() -> Path:
    return Path(_env("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / __package_name()


def data_dir() -> Path:
    return Path(_env("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / __package_name()


def cache_dir() -> Path:
    return Path(_env("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / __package_name()


def __package_name() -> str:
    from . import APP_NAME

    return APP_NAME


def settings_file() -> Path:
    return config_dir() / "settings.conf"


def history_file() -> Path:
    return data_dir() / "history.jsonl"


def queue_file() -> Path:
    return data_dir() / "queue.json"


def log_dir() -> Path:
    return cache_dir() / "logs"


def staging_dir() -> Path:
    return data_dir() / "staging"


def archives_dir() -> Path:
    return data_dir() / "archives"


def default_download_dir() -> Path:
    """~/Videos, or the XDG user videos directory when available."""
    try:
        from .utils import xdg_user_dir

        videos = xdg_user_dir("VIDEOS")
        if videos:
            return Path(videos)
    except Exception:
        pass
    return Path.home() / "Videos"


def ensure_dirs() -> None:
    for directory in (
        config_dir(),
        data_dir(),
        cache_dir(),
        log_dir(),
        staging_dir(),
        archives_dir(),
        default_download_dir(),
    ):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Best effort; the GUI reports writable failures at runtime.
            pass
