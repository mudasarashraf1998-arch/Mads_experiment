"""MEGA adapter: MEGAcmd (mega-get) subprocess with staging and resume."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from .adapter import BaseAdapter, DownloadOptions, AdapterResult
from ..utils import redact, safe_name
from ..paths import staging_dir
from ..history import append as history_append, is_completely_done

_LINK_RE = re.compile(r"mega\.(?:nz|io|co\.nz)/(?:file|folder)/([A-Za-z0-9_-]+)")
_KEY_RE = re.compile(r"[#!]([A-Za-z0-9_-]{6,})")
_PERCENT_RE = re.compile(r"(\d{1,3})%")


def parse_link(url: str) -> Optional[tuple[str, str]]:
    """Return (kind, id) for a MEGA link, or None."""
    if "/folder/" in url or "#F!" in url:
        kind = "folder"
    elif "/file/" in url or "#!" in url:
        kind = "file"
    else:
        return None
    m = _LINK_RE.search(url)
    if not m:
        m = _KEY_RE.search(url)
    if not m:
        return None
    id_ = m.group(1).split("?")[0].split("#")[0].split("&")[0]
    return kind, id_


class MegaAdapter(BaseAdapter):
    name = "mega"
    required_tool = "mega-get"

    def __init__(self, options: DownloadOptions):
        super().__init__(options)
        self.url = options.extra.get("url", "")

    def probe(self, url: str) -> dict:
        parsed = parse_link(url)
        if not parsed:
            return {"ok": False, "error": "This MEGA link is not in a recognised format."}
        kind, id_ = parsed
        return {
            "ok": True,
            "id": id_,
            "kind": "Folder" if kind == "folder" else "File",
            "title": f"MEGA-{id_}",
        }

    def run(self, on_progress: Optional[Callable[[dict], None]] = None,
            on_output: Optional[Callable[[str], None]] = None) -> AdapterResult:
        url = self.url
        info = self.probe(url)
        if not info.get("ok"):
            history_append(url, "mega", info.get("kind", "file"), "", "failed")
            return AdapterResult(state="failed", error=info.get("error", "MEGA link parse failed"))

        kind = info["kind"]
        id_ = info["id"]
        title = info["title"]

        if is_completely_done(url):
            return self._record_skip(url, kind, self._destination_for(url, title))

        if not shutil.which("mega-get"):
            history_append(url, "mega", kind, "", "failed")
            return AdapterResult(state="failed", error="MEGAcmd (mega-get) is not installed.")

        staging = staging_dir() / f"mega-{id_}"
        staging.mkdir(parents=True, exist_ok=True)

        args = ["mega-get", url, str(staging)]

        from .runner import SubprocessRunner

        def parse_line(line: str) -> Optional[dict]:
            match = _PERCENT_RE.search(line)
            if match:
                return {"percent": float(match.group(1)), "message": line.strip()}
            return None

        runner = SubprocessRunner(args, on_output=on_output, on_progress=on_progress,
                                  parse_line=parse_line)
        self._runner = runner
        runner.start()
        result = runner.wait()

        if result.state == "cancelled":
            return AdapterResult(state="cancelled", error="Cancelled by user.")

        # Name the destination: inner folder if staging holds exactly one,
        # otherwise the id-based fallback.
        entries = [p for p in staging.iterdir()] if staging.is_dir() else []
        inner_dirs = [p for p in entries if p.is_dir()]
        if len(inner_dirs) == 1:
            default_name = inner_dirs[0].name
        else:
            default_name = title

        dest = self._destination_for(url, default_name)
        Path(dest).mkdir(parents=True, exist_ok=True)

        moved = 0
        if staging.is_dir():
            for child in list(staging.iterdir()):
                target = Path(dest) / child.name
                if target.exists():
                    from ..utils import unique_path
                    target = unique_path(target)
                child.rename(target)
                moved += 1
        try:
            staging.rmdir()
        except OSError:
            pass

        files = [p for p in Path(dest).rglob("*")
                 if p.is_file() and p.name != ".ud-complete"] if Path(dest).is_dir() else []
        if not files:
            history_append(url, "mega", kind, dest, "failed")
            return AdapterResult(
                state="failed", destination=dest,
                error="MEGAcmd finished but no files arrived. Check the log.",
            )
        size = sum(p.stat().st_size for p in files)
        (Path(dest) / ".ud-complete").touch(exist_ok=True)
        history_append(url, "mega", kind, dest, "ok")
        return AdapterResult(state="completed", destination=dest, files=len(files), size=size)

    def runner_pause(self) -> bool:
        return self._runner.pause() if self._runner else False

    def runner_resume(self) -> bool:
        return self._runner.resume() if self._runner else False

    def stop(self) -> None:
        pass

    def classify_error(self, returncode: int, output: str) -> str:
        text = (output or "").lower()
        if any(token in text for token in ("invalid", "not found", "does not exist", "bad link",
                                           "quota", "bandwidth", "over quota")):
            return "fatal"
        return "transient"
