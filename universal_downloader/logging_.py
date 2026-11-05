"""Per-run log files in ~/.cache/universal-downloader/logs.

Secrets never reach the log: every message is redacted first.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from threading import Lock

from .utils import redact

_LOG_FILE: Path | None = None
_LOCK = Lock()


def init_log_file(path: Path | None = None) -> Path:
    from .paths import log_dir

    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = path or (log_dir() / f"download-{stamp}-{os.getpid()}.log")
    global _LOG_FILE
    with _LOCK:
        _LOG_FILE = path
    try:
        path.touch(exist_ok=True)
    except OSError:
        with _LOCK:
            _LOG_FILE = None
    return path  # type: ignore[return-value]


def log_file() -> Path | None:
    with _LOCK:
        return _LOG_FILE


def log(level: str, message: str) -> None:
    path = log_file()
    if not path:
        return
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {level:<7s} {redact(message)}\n"
    with _LOCK:
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError:
            pass

def info(message: str) -> None:
    log("INFO", message)


def warn(message: str) -> None:
    log("WARN", message)


def error(message: str) -> None:
    log("ERROR", message)


def debug(message: str) -> None:
    log("DEBUG", message)


def output(message: str) -> None:
    """Record a downloader subprocess output line."""
    log("OUTPUT", message)
