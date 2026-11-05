"""Download history.

One JSON object per attempt, appended to
~/.local/share/universal-downloader/history.jsonl.
URLs are redacted before being stored.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import history_file
from .utils import redact

_STATUS_ORDER = {"ok": 0, "failed": 1, "cancelled": 2}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def append(
    url: str,
    source: str,
    kind: str,
    destination: str = "",
    status: str = "pending",
) -> None:
    path = history_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "timestamp": _now(),
        "source": source,
        "type": kind,
        "url": redact(url),
        "destination": destination,
        "status": status,
    }
    line = json.dumps(entry, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_all() -> list[dict[str, Any]]:
    path = history_file()
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                entries.append({"raw": line})
    return entries


def last_destination(url: str) -> str | None:
    """Return the destination of the most recent attempt for this URL."""
    path = history_file()
    if not path.exists():
        return None
    key = redact(url)
    result: str | None = None
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("url") == key and entry.get("destination"):
                    result = entry["destination"]
    except OSError:
        return None
    return result


def last_status(url: str) -> str | None:
    """Return the status of the most recent attempt for this URL."""
    path = history_file()
    if not path.exists():
        return None
    key = redact(url)
    result: str | None = None
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("url") == key:
                    result = entry.get("status")
    except OSError:
        return None
    return result


def is_completely_done(url: str, force: bool = False) -> bool:
    """True if the latest attempt succeeded and its files still exist."""
    if force:
        return False
    status = last_status(url)
    if status != "ok":
        return False
    dest = last_destination(url)
    if not dest:
        return False
    path = Path(dest)
    if path.is_file():
        return path.stat().st_size > 0
    if path.is_dir():
        marker = path / ".ud-complete"
        if not marker.exists():
            return False
        # Never claim a folder is complete while partials remain.
        for partial in path.rglob("*"):
            if partial.is_file() and partial.suffix in (".part", ".aria2"):
                return False
        return True
    return False
