"""Google Drive adapter: gdown subprocess with resume, skip and verification."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from .adapter import BaseAdapter, DownloadOptions, AdapterResult
from ..utils import redact, safe_name
from ..history import append as history_append, is_completely_done

_ID_RE = re.compile(
    r"(?:/folders/|/file/d/|[?&]id=)([A-Za-z0-9_-]+)")
_PERCENT_RE = re.compile(r"(?<!\d)(\d{1,3})%\s*\|\s*[\d./\sA-Za-z]*")


def extract_id(url: str) -> Optional[str]:
    match = _ID_RE.search(url)
    if not match:
        return None
    return match.group(1).split("?")[0].split("#")[0].split("&")[0]


class GDriveAdapter(BaseAdapter):
    name = "gdrive"
    required_tool = "gdown"

    def __init__(self, options: DownloadOptions):
        super().__init__(options)
        self.kind = options.extra.get("kind", "File")
        self.url = options.extra.get("url", "")

    # ---------------------------------------------------------------- probe

    def probe(self, url: str) -> dict:
        file_id = extract_id(url)
        if not file_id:
            return {"ok": False, "error": "This Google Drive link does not contain a file or folder id."}
        kind = "Folder" if "/folders/" in url or "/folder/" in url or "#folders" in url else "File"
        title = None
        if shutil.which("curl"):
            try:
                result = subprocess.run(
                    ["curl", "-sSL", "--max-time", "20",
                     "-A", "Mozilla/5.0 universal-downloader/2.0.2", url],
                    capture_output=True, text=True, timeout=25,
                )
                html = result.stdout[:200000]
                if html:
                    m = re.search(r"<title[^>]*>([^<]*)</title>", html, re.IGNORECASE | re.DOTALL)
                    if m:
                        title = m.group(1).strip()
                        title = re.sub(r"\s+", " ", title)
                        for suffix in (" - Google Drive", " – Google Drive", " — Google Drive"):
                            if title.endswith(suffix):
                                title = title[:-len(suffix)].strip()
                        bad = ("", "Google Drive", "One place for all your files",
                               "Virus scan warning", "Sign in")
                        if title in bad:
                            title = None
            except (OSError, subprocess.SubprocessError):
                title = None
        return {
            "ok": True,
            "id": file_id,
            "kind": kind,
            "title": title or f"Google-Drive-{file_id}",
        }

    # ---------------------------------------------------------------- run

    def run(self, on_progress: Optional[Callable[[dict], None]] = None,
            on_output: Optional[Callable[[str], None]] = None) -> AdapterResult:
        url = self.url
        info = self.probe(url)
        if not info.get("ok"):
            history_append(url, "gdrive", self.kind, "", "failed")
            return AdapterResult(state="failed", error=info.get("error", "Drive probe failed"))

        file_id = info["id"]
        kind = info["kind"]
        title = info["title"]
        dest = self._destination_for(url, title)
        Path(dest).mkdir(parents=True, exist_ok=True)

        if is_completely_done(url):
            return self._record_skip(url, kind, dest)

        if not shutil.which("gdown"):
            history_append(url, "gdrive", kind, dest, "failed")
            return AdapterResult(state="failed", error="gdown is not installed.")

        args = ["gdown"]
        if shutil.which("gdown"):
            # --continue support varies by version; probe is done at runtime.
            help_output = subprocess.run(
                ["gdown", "--help"], capture_output=True, text=True, timeout=15,
            ).stdout + subprocess.run(["gdown", "--help"], capture_output=True, text=True, timeout=15).stderr
            if "--continue" in help_output:
                args.append("--continue")
        if kind == "Folder":
            args += ["--folder"]
        args += ["-O", dest, url]

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
            return AdapterResult(state="cancelled", destination=dest, error="Cancelled by user.")

        # Flatten a single id-named wrapper folder gdown sometimes creates.
        only = list(Path(dest).iterdir())
        if len(only) == 1 and only[0].is_dir() and file_id in only[0].name:
            for child in only[0].iterdir():
                child.rename(Path(dest) / child.name)
            try:
                only[0].rmdir()
            except OSError:
                pass

        partials = [p for p in Path(dest).rglob("*")
                    if p.is_file() and p.suffix in (".part", ".aria2")]
        if partials:
            history_append(url, "gdrive", kind, dest, "failed")
            return AdapterResult(
                state="failed", destination=dest,
                error="Incomplete files left behind; completed files were kept.",
            )

        files = [p for p in Path(dest).rglob("*")
                 if p.is_file() and p.name != ".ud-complete"]
        if not files:
            history_append(url, "gdrive", kind, dest, "failed")
            return AdapterResult(state="failed", destination=dest,
                                 error="gdown reported success but no files arrived.")
        size = sum(p.stat().st_size for p in files)
        (Path(dest) / ".ud-complete").touch(exist_ok=True)
        history_append(url, "gdrive", kind, dest, "ok")
        return AdapterResult(state="completed", destination=dest, files=len(files), size=size)

    def runner_pause(self) -> bool:
        return self._runner.pause() if self._runner else False

    def runner_resume(self) -> bool:
        return self._runner.resume() if self._runner else False

    def stop(self) -> None:
        pass

    def classify_error(self, returncode: int, output: str) -> str:
        text = (output or "").lower()
        if any(token in text for token in ("quota", "rate limit", "permission", "access denied",
                                           "not found", "404", "private")):
            return "fatal"
        return "transient"
