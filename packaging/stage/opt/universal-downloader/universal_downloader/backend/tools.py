"""Detection of the external downloader tools.

Nothing is bundled: the GUI detects what is installed and explains clearly
what is missing, mirroring the existing terminal backend's doctor.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

TOOL_HINTS = {
    "yt-dlp": "sudo apt install yt-dlp  (or: python3 -m pip install --user --upgrade yt-dlp)",
    "gdown": "python3 -m pip install --user --upgrade gdown",
    "mega-get": ("Install MEGAcmd from https://mega.io/cmd "
                 "(Ubuntu/Debian .deb: sudo apt install ./megacmd-*.deb)"),
    "aria2c": "sudo apt install aria2",
    "ffmpeg": "sudo apt install ffmpeg",
    "curl": "sudo apt install curl",
}

TOOL_PURPOSE = {
    "yt-dlp": "YouTube",
    "gdown": "Google Drive",
    "mega-get": "MEGA",
    "aria2c": "direct file links",
    "ffmpeg": "merging YouTube video+audio and audio conversion (recommended)",
    "curl": "file names and Drive titles (recommended)",
}

REQUIRED_TOOLS = ("yt-dlp", "gdown", "mega-get", "aria2c")


@dataclass
class ToolInfo:
    name: str
    available: bool
    version: str = ""
    purpose: str = ""
    hint: str = ""
    required: bool = False


def which(name: str) -> Optional[str]:
    return shutil.which(name)


def version(name: str) -> str:
    try:
        result = subprocess.run(
            [name, "--version"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    output = (result.stdout or result.stderr or "").strip()
    output = output.splitlines()[0] if output else ""
    return "".join(ch for ch in output if ch.isprintable())[:64]


def probe_all() -> dict[str, ToolInfo]:
    """Return a ToolInfo for every tool the application knows about."""
    tools: dict[str, ToolInfo] = {}
    for name in sorted(set(list(TOOL_HINTS) + list(TOOL_PURPOSE))):
        available = which(name) is not None
        tools[name] = ToolInfo(
            name=name,
            available=available,
            version=version(name) if available else "",
            purpose=TOOL_PURPOSE.get(name, ""),
            hint=TOOL_HINTS.get(name, ""),
            required=name in REQUIRED_TOOLS,
        )
    return tools


def required_missing() -> list[ToolInfo]:
    return [t for t in probe_all().values() if t.required and not t.available]


def source_tool(source: str) -> str:
    return {"youtube": "yt-dlp", "gdrive": "gdown", "mega": "mega-get", "direct": "aria2c"}.get(source, "")
