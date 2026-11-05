"""Shared helpers: byte formatting, redaction, safe names, URL validation."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


# ------------------------------------------------------------------ bytes


def human_bytes(num) -> str:
    try:
        b = float(num)
    except (TypeError, ValueError):
        return "?"
    if b < 0:
        b = 0.0
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while b >= 1024 and i < len(units) - 1:
        b /= 1024
        i += 1
    if i == 0:
        return f"{int(b)} {units[i]}"
    return f"{b:.1f} {units[i]}"


def parse_bytes(text: str) -> int:
    """Parse '1.5GB', '1024', '5M' style strings into bytes."""
    text = text.strip().replace(",", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([KMGT]i?B?|B)?", text, re.IGNORECASE)
    if not match:
        return 0
    value = float(match.group(1))
    unit = (match.group(2) or "B").upper()
    multipliers = {
        "B": 1,
        "KB": 1000,
        "MB": 1000 ** 2,
        "GB": 1000 ** 3,
        "TB": 1000 ** 4,
        "KIB": 1024,
        "MIB": 1024 ** 2,
        "GIB": 1024 ** 3,
        "TIB": 1024 ** 4,
        "K": 1000,
        "M": 1000 ** 2,
        "G": 1000 ** 3,
        "T": 1000 ** 4,
    }
    return int(value * multipliers.get(unit, 1))


def format_speed(bytes_per_sec) -> str:
    try:
        bps = float(bytes_per_sec)
    except (TypeError, ValueError):
        return "--"
    if bps < 0:
        bps = 0.0
    if bps < 1024:
        return f"{bps:.0f} B/s"
    return human_bytes(bps) + "/s"


def format_eta(seconds) -> str:
    try:
        secs = int(float(seconds))
    except (TypeError, ValueError):
        return "--"
    if secs < 0:
        secs = 0
    hours, remainder = divmod(secs, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


# ------------------------------------------------------------------ redaction


_REDACTION_RULES = [
    # user:pass@host
    (re.compile(r"(https?://)[^/\s@]+:[^/\s@]+@"), r"\1<hidden>@"),
    # MEGA decryption keys (#... / !... long tokens)
    (re.compile(r"(mega\.(?:nz|io|co\.nz)[^\s]*[#!])[A-Za-z0-9_-]{6,}"), r"\1<hidden>"),
    (re.compile(r"(#[A-Za-z0-9_-]{16,})"), "<hidden>"),
    # sensitive query parameters
    (
        re.compile(
            r"([?&](key|token|auth|authorization|password|passwd|sig|signature|"
            r"api[_-]?key|secret|session|hash)=)[^&\s]+",
            re.IGNORECASE,
        ),
        r"\1<hidden>",
    ),
    # Cookie: headers
    (re.compile(r"([Cc]ookie:\s*)[^\s]+"), r"\1<hidden>"),
]


def redact(text: str) -> str:
    """Redact secrets from a string before it is logged or stored."""
    if not text:
        return text
    result = text
    for pattern, replacement in _REDACTION_RULES:
        result = pattern.sub(replacement, result)
    return result


def redact_url(url: str) -> str:
    return redact(url)


# ------------------------------------------------------------------ names


_INVALID_NAME_CHARS = re.compile(r'[/\\:*?"<>|\r\n\t]')


def safe_name(name: str, max_length: int = 150) -> str:
    """Make a string safe as a file/folder name (mirrors the shell backend)."""
    if not name:
        return "untitled"
    name = name.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    name = _INVALID_NAME_CHARS.sub(" - ", name)
    name = re.sub(r"[^\x20-\x7E]", "", name)
    name = re.sub(r"[ \t]+", " ", name)
    name = name.strip(" .-")
    name = name[:max_length]
    if name in (".", "..") or not name:
        name = "untitled"
    return name


def unique_path(base: Path) -> Path:
    """Return a non-existing path by appending (1), (2), ... before the suffix."""
    if not base.exists():
        return base
    stem, suffix = base.stem, base.suffix
    counter = 1
    while True:
        candidate = base.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


# ------------------------------------------------------------------ URLs


_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


def is_valid_url(url: str) -> bool:
    if not url or " " in url or "\n" in url or "\r" in url:
        return False
    return bool(_URL_RE.match(url.strip()))


def url_host(url: str) -> str:
    try:
        host = url.split("://", 1)[1]
        host = host.split("/", 1)[0]
        host = host.split("?", 1)[0]
        host = host.split("#", 1)[0]
        host = host.rsplit("@", 1)[-1]
        host = host.rsplit(":", 1)[0]
        return host.lower()
    except (AttributeError, ValueError):
        return ""


def url_basename(url: str) -> str:
    url = url.split("#", 1)[0].split("?", 1)[0]
    name = url.rsplit("/", 1)[-1]
    if not name:
        return "download"
    try:
        return bytes(name, "utf-8").decode("unicode_escape") if "%" in name else name
    except Exception:
        return name


def xdg_user_dir(key: str) -> Optional[str]:
    """Return an XDG user directory via xdg-user-dir when available."""
    try:
        result = subprocess.run(
            ["xdg-user-dir", key],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode == 0:
        path = result.stdout.strip()
        if path and os.path.isabs(path):
            return path
    return None


def free_bytes(folder: str | Path) -> Optional[int]:
    try:
        usage = shutil.disk_usage(folder)
        return usage.free
    except OSError:
        return None
