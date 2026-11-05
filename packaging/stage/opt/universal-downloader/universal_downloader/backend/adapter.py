"""Base adapter for download backends.

Every supported source is one adapter, mirroring one module of the existing
terminal backend (modules/youtube.sh, google-drive.sh, mega.sh, direct.sh).
Adapters never touch the GUI: they run a subprocess, parse real progress and
report structured results. The job controller (qt side) owns the Qt objects.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..utils import human_bytes, safe_name
from ..paths import archives_dir, staging_dir
from .tools import source_tool


@dataclass
class DownloadOptions:
    """Generic options; source-specific keys are stored in `extra`."""
    source: str = "direct"
    destination: str = ""
    title: str = ""
    extra: dict = field(default_factory=dict)

    def get(self, key, default=None):
        return self.extra.get(key, default)


@dataclass
class AdapterResult:
    state: str  # "completed" | "failed" | "cancelled"
    destination: str = ""
    files: int = 0
    size: int = 0
    error: str = ""
    skip_reason: str = ""


class BaseAdapter:
    name: str = "base"
    required_tool: str = ""

    def __init__(self, options: DownloadOptions):
        self.options = options
        self.cancelled = False

    # ---------------------------------------------------------------- tooling

    @classmethod
    def tool_available(cls) -> bool:
        return shutil.which(cls.required_tool) is not None if cls.required_tool else True

    @classmethod
    def tool_hint(cls) -> str:
        from .tools import TOOL_HINTS
        return TOOL_HINTS.get(cls.required_tool, f"Install {cls.required_tool}")

    # ---------------------------------------------------------------- lifecycle

    def probe(self, url: str) -> dict:
        """Pre-download inspection: title, kind, size. Source-specific."""
        raise NotImplementedError

    def run(self, on_progress: Optional[Callable[[dict], None]] = None,
            on_output: Optional[Callable[[str], None]] = None) -> AdapterResult:
        """Execute the download. Must not be called concurrently for one job."""
        raise NotImplementedError

    def stop(self) -> None:
        self.cancelled = True

    # ---------------------------------------------------------------- helpers

    def _destination_for(self, url: str, default_name: str) -> str:
        """Reuse the last destination for this link, else build a fresh one."""
        from ..history import last_destination, is_completely_done

        dest = last_destination(url)
        if dest:
            return dest
        base = Path(self.options.destination) / safe_name(default_name)
        return str(base)

    def _record_skip(self, url: str, kind: str, destination: str) -> AdapterResult:
        from ..history import append as history_append
        history_append(url, self.options.source, kind, destination, "ok")
        return AdapterResult(
            state="completed", destination=destination,
            skip_reason="Already downloaded",
        )
