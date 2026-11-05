"""Direct file links: aria2c subprocess with resume, skip and verification."""

from __future__ import annotations

import re
import shutil
import subprocess
import time
import threading
from pathlib import Path
from typing import Callable, Optional

from .adapter import BaseAdapter, DownloadOptions, AdapterResult
from .runner import SubprocessRunner
from ..utils import human_bytes, redact, safe_name, url_basename, free_bytes, unique_path
from ..history import append as history_append, is_completely_done

_HEAD_RE = re.compile(r"(?i)^content-length:\s*(\d+)", re.MULTILINE)
_DISPOSITION_RE = re.compile(r"(?i)^content-disposition:\s*(.+)$")
_FILENAME_RE = re.compile(r"(?i)filename\*?=(?:UTF-8'')?['\"]?([^'\"\\;]+)")


def probe(url: str) -> dict:
    """Ask the server for the real file name and size. Returns size/name."""
    info = {"size": 0, "name": url_basename(url)}
    if not shutil.which("curl"):
        return info
    try:
        result = subprocess.run(
            ["curl", "-sIL", "--max-time", "20",
             "-A", "Mozilla/5.0 (X11; Linux x86_64) universal-downloader/2.0.2", url],
            capture_output=True, text=True, timeout=25,
        )
    except (OSError, subprocess.SubprocessError):
        return info
    headers = result.stdout
    match = _HEAD_RE.search(headers)
    if match:
        try:
            info["size"] = int(match.group(1))
        except ValueError:
            info["size"] = 0
    for line in headers.splitlines():
        disp = _DISPOSITION_RE.match(line.strip())
        if disp:
            name_match = _FILENAME_RE.search(disp.group(1))
            if name_match:
                info["name"] = name_match.group(1).strip()
    if not info["name"]:
        info["name"] = url_basename(url)
    return info


_ARIA2_RE = re.compile(r"<length>(\d+)</length>.*?<totalLength>(\d+)</totalLength>", re.S)


class DirectAdapter(BaseAdapter):
    name = "direct"
    required_tool = "aria2c"

    def __init__(self, options: DownloadOptions):
        super().__init__(options)
        self.url = options.extra.get("url", "")

    def run(self, on_progress: Optional[Callable[[dict], None]] = None,
            on_output: Optional[Callable[[str], None]] = None) -> AdapterResult:
        url = self.url
        info = probe(url)
        size = info["size"]
        name = safe_name(info["name"])

        if not shutil.which("aria2c"):
            history_append(url, "direct", "file", "", "failed")
            return AdapterResult(state="failed", error="aria2c is not installed.")

        connections = int(self.options.extra.get("direct_connections", 4))
        dest_dir = Path(self.options.destination) / "Direct Downloads"
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / name

        # Skip only when the server told us the size and the local file matches.
        if size > 0 and target.exists() and target.stat().st_size == size:
            history_append(url, "direct", "file", str(target), "ok")
            return AdapterResult(state="completed", destination=str(target),
                                 files=1, size=size, skip_reason="Already downloaded")
        if target.exists() and size == 0:
            # Unknown remote size: never assume a local file is complete.
            held = unique_path(Path(str(target) + ".ud-incomplete"))
            try:
                target.rename(held)
            except OSError:
                pass

        if target.with_suffix(target.suffix + ".aria2").exists():
            pass  # aria2 --continue resumes from the control file

        # Space sanity check when the size is known.
        if size > 0:
            free = free_bytes(dest_dir)
            if free is not None and free < size:
                history_append(url, "direct", "file", str(dest_dir), "failed")
                return AdapterResult(
                    state="failed",
                    error=f"Not enough storage space: need about {human_bytes(size)}, "
                          f"free {human_bytes(free)}.",
                )

        args = [
            "aria2c", "--continue=true", f"--max-tries={self.options.extra.get('retries', 5)}",
            f"--retry-wait={self.options.extra.get('retry_wait', 10)}",
            "--connect-timeout=30", "--timeout=60",
            f"--max-connection-per-server={connections}",
            f"--split={connections}", "--min-split-size=1M",
            "--max-concurrent-downloads=1", "--auto-file-renaming=false",
            "--allow-overwrite=false", "--file-allocation=none",
            "--remote-time=true", "--content-disposition-default-utf8=true",
            "--console-log-level=warn", "--summary-interval=1",
            "--human-readable=true", f"--dir={dest_dir}", f"--out={name}", url,
        ]

        control = target.with_name(target.name + ".aria2")
        last_completed = 0
        last_time = time.monotonic()

        def read_control() -> Optional[dict]:
            try:
                text = control.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
            match = _ARIA2_RE.search(text)
            if not match:
                return None
            completed = int(match.group(1))
            total = int(match.group(2))
            now = time.monotonic()
            nonlocal last_completed, last_time
            speed = 0.0
            if now > last_time:
                speed = (completed - last_completed) / (now - last_time)
            last_completed = completed
            last_time = now
            percent = (completed / total * 100) if total else 0.0
            return {
                "percent": min(100.0, percent),
                "downloaded": completed,
                "total": total,
                "speed": max(0.0, speed),
                "message": f"{human_bytes(completed)} / {human_bytes(total)}",
            }

        runner = SubprocessRunner(args, on_output=on_output, on_progress=on_progress,
                                  parse_line=lambda line: None)
        self._runner = runner
        runner.start()
        # aria2c does not emit line-by-line progress, so sample the control file
        # about once per second (worker thread only, never the GUI thread).
        def sampler() -> None:
            while not runner.is_cancelled:
                update = read_control()
                if update and on_progress:
                    on_progress(update)
                if runner.process is not None and runner.poll() is not None:
                    update = read_control()
                    if update and on_progress:
                        on_progress(update)
                    break
                time.sleep(1.0)

        sampler_thread = threading.Thread(target=sampler, daemon=True)
        sampler_thread.start()
        result = runner.wait()
        sampler_thread.join(timeout=2)

        if result.state == "cancelled":
            return AdapterResult(state="cancelled", destination=str(target), error="Cancelled by user.")

        aria2_remained = control.exists()
        if target.exists() and not aria2_remained:
            actual = target.stat().st_size
            history_append(url, "direct", "file", str(target), "ok")
            return AdapterResult(state="completed", destination=str(target),
                                 files=1, size=actual)
        if target.exists() and aria2_remained:
            history_append(url, "direct", "file", str(target), "failed")
            return AdapterResult(
                state="failed", destination=str(target),
                error="Incomplete: the partial file and its control file are kept for resume.",
            )
        history_append(url, "direct", "file", str(dest_dir), "failed")
        return AdapterResult(state="failed", destination=str(dest_dir),
                             error="Download did not produce a file.")

    def runner_pause(self) -> bool:
        return self._runner.pause() if self._runner else False

    def runner_resume(self) -> bool:
        return self._runner.resume() if self._runner else False

    def stop(self) -> None:
        pass

    def classify_error(self, returncode: int, output: str) -> str:
        return "transient"
