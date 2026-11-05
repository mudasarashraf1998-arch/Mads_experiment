"""YouTube adapter: yt-dlp subprocess, real progress, resume and archive."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .adapter import BaseAdapter, DownloadOptions, AdapterResult
from ..utils import human_bytes, redact, safe_name
from ..paths import archives_dir
from ..history import append as history_append, is_completely_done

META_PRINT = "%(playlist_title|)s\t%(playlist_index|0)s\t%(id|)s\t%(title|)s"

# [download] 10.1% of ~ 45.23MiB at 2.10MiB/s ETA 0:15
_PROGRESS_RE = re.compile(
    r"\[download\]\s+"
    r"(?P<percent>\d+(?:\.\d+)?)%\s+"
    r"of\s+(?:~\s+)?"
    r"(?P<total>[\d.,]+)\s*(?P<tunit>[KMG]?i?B)?\s+"
    r"at\s+(?P<speed>[\d.,]+)\s*(?P<sunit>[KMG]?i?B)/s\s+"
    r"ETA\s+(?P<eta>\S+)",
    re.IGNORECASE,
)
_BYTES_RE = re.compile(r"([\d.,]+)\s*([KMG]?i?B)", re.IGNORECASE)


def _parse_size(text: str) -> int:
    match = _BYTES_RE.fullmatch(text.strip())
    if not match:
        return 0
    value = float(match.group(1).replace(",", ""))
    unit = match.group(2).upper()
    multipliers = {
        "B": 1, "KB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3, "TB": 1000 ** 4,
        "KIB": 1024, "MIB": 1024 ** 2, "GIB": 1024 ** 3, "TIB": 1024 ** 4,
    }
    return int(value * multipliers.get(unit, 1))


@dataclass
class YouTubeOptions(DownloadOptions):
    source: str = "youtube"
    yt_mode: str = "video"          # video | audio
    yt_quality: str = "best"        # best | 2160 | 1440 | 1080 | 720 | 480 | 360
    yt_container: str = "mkv"       # mp4 | mkv
    yt_audio: str = "best"          # best | mp3-320 | mp3-192 | mp3-128
    yt_playlist: str = "full"       # single | full
    yt_numbering: bool = True
    yt_archive: bool = True


class YouTubeAdapter(BaseAdapter):
    name = "youtube"
    required_tool = "yt-dlp"

    def __init__(self, options: DownloadOptions):
        super().__init__(options)
        extra = options.extra or {}
        self.mode = extra.get("yt_mode", "video")
        self.quality = extra.get("yt_quality", "best")
        self.container = extra.get("yt_container", "mkv")
        self.audio = extra.get("yt_audio", "best")
        self.playlist = extra.get("yt_playlist", "full")
        self.numbering = bool(extra.get("yt_numbering", True))
        self.archive = bool(extra.get("yt_archive", True))
        self._runner_proc = None

    # ---------------------------------------------------------------- probe

    def probe(self, url: str) -> dict:
        if not shutil.which("yt-dlp"):
            return {"ok": False, "error": "yt-dlp is not installed"}
        cmd = [
            "yt-dlp", "--no-warnings", "--ignore-config", "--skip-download",
            "--flat-playlist", "--print", META_PRINT, url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "error": str(exc)}
        if result.returncode != 0:
            return {"ok": False, "error": "Could not read information about this YouTube link."}
        entries = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            while len(parts) < 4:
                parts.append("")
            entries.append({
                "playlist_title": parts[0],
                "index": parts[1],
                "id": parts[2],
                "title": parts[3],
            })
        if not entries:
            return {"ok": False, "error": "YouTube returned no video for this link."}
        playlist_title = entries[0]["playlist_title"] or ""
        first = entries[0]
        return {
            "ok": True,
            "count": len(entries),
            "playlist_title": playlist_title,
            "first_id": first["id"],
            "first_title": first["title"],
            "entries": entries,
        }

    # ---------------------------------------------------------------- format args

    def _yt_format_args(self, have_ffmpeg: bool) -> list[str]:
        args: list[str] = []
        if self.mode == "audio":
            if self.audio == "best":
                # Preserve the original audio stream; no conversion.
                args += ["--format", "ba/b"]
            elif have_ffmpeg:
                audio_format = "mp3" if self.audio.startswith("mp3") else self.audio
                args += ["--extract-audio", "--audio-format", audio_format]
                if self.audio == "mp3-320":
                    args += ["--audio-quality", "0"]
                elif self.audio == "mp3-192":
                    args += ["--audio-quality", "3"]
                elif self.audio == "mp3-128":
                    args += ["--audio-quality", "6"]
            else:
                args += ["--format", "ba/b"]
            return args
        if have_ffmpeg:
            height = ""
            if self.quality != "best":
                height = self.quality
            args += [
                "--format", f"bv*[height<={height}]+ba/b[height<={height}]/b[height<={height}]" if height else "bv*+ba/b",
                "--merge-output-format", self.container,
            ]
        else:
            args += ["--format", "b"]
        return args

    def _outtmpl(self, dest: str) -> str:
        if self.playlist == "full" and self.numbering:
            return os.path.join(dest, "%(playlist_index)02d - %(title)s [%(id)s].%(ext)s")
        if self.playlist == "full":
            return os.path.join(dest, "%(title)s [%(id)s].%(ext)s")
        return os.path.join(dest, "%(title)s [%(id)s].%(ext)s")

    # ---------------------------------------------------------------- run

    def run(self, on_progress: Optional[Callable[[dict], None]] = None,
            on_output: Optional[Callable[[str], None]] = None) -> AdapterResult:
        url = self.options.url if hasattr(self.options, "url") else ""
        # url is carried in options.extra by the job controller
        url = self.options.extra.get("url", "")
        have_ffmpeg = shutil.which("ffmpeg") is not None

        info = self.probe(url)
        if not info.get("ok"):
            history_append(url, "youtube", info.get("kind", "video"), "", "failed")
            return AdapterResult(state="failed", error=info.get("error", "YouTube probe failed"))

        kind = "Playlist" if info["count"] > 1 else "Video"
        title = info["playlist_title"] or info["first_title"] or f"YouTube-{info['first_id']}"
        dest = self._destination_for(url, title)
        Path(dest).mkdir(parents=True, exist_ok=True)

        if is_completely_done(url):
            return self._record_skip(url, kind, dest)

        outtmpl = self._outtmpl(dest)
        archive = str(archives_dir() / "ytdlp-archive.txt") if self.archive else "none"

        retries = str(self.options.extra.get("retries", 5))
        fragments = str(self.options.extra.get("yt_fragments", 4))
        args = [
            "yt-dlp", "--newline", "--no-colors", "--continue", "--no-overwrites",
            "--no-mtime", "--retries", retries, "--fragment-retries", retries,
            "--concurrent-fragments", fragments,
        ]
        if self.archive:
            args += ["--download-archive", archive]
        if have_ffmpeg and self.mode != "audio":
            args += ["--embed-metadata"]
        args += self._yt_format_args(have_ffmpeg)
        args += ["--output", outtmpl, url]

        if not have_ffmpeg and self.mode == "video":
            on_output and on_output("[notice] ffmpeg not installed: downloading best single file (no merge).")
        if self.mode == "audio" and self.audio != "best" and not have_ffmpeg:
            on_output and on_output("[notice] ffmpeg not installed: keeping original audio stream.")

        from .runner import SubprocessRunner
        runner = SubprocessRunner(
            args,
            on_output=on_output,
            on_progress=on_progress,
            parse_line=self._parse_line,
        )
        self._runner = runner
        runner.start()
        result = runner.wait()
        self._runner_proc = None

        if result.state == "cancelled":
            return AdapterResult(state="cancelled", destination=dest, error="Cancelled by user.")
        if result.returncode not in (0, None) and result.state == "failed":
            # yt-dlp may exit non-zero while some files finished; verify disk.
            pass

        partial = next(Path(dest).rglob("*.part"), None) if Path(dest).is_dir() else None
        if partial:
            history_append(url, "youtube", kind, dest, "failed")
            return AdapterResult(
                state="failed", destination=dest,
                error="Incomplete file left behind; finished files were kept.",
            )

        files = [p for p in Path(dest).iterdir() if p.is_file() and p.name != ".ud-complete"]
        if not files:
            history_append(url, "youtube", kind, dest, "failed")
            return AdapterResult(state="failed", destination=dest, error="No completed files found.")
        size = sum(p.stat().st_size for p in files)
        history_append(url, "youtube", kind, dest, "ok")
        return AdapterResult(state="completed", destination=dest, files=len(files), size=size)

    def runner_pause(self) -> bool:
        return self._runner.pause() if self._runner else False

    def runner_resume(self) -> bool:
        return self._runner.resume() if self._runner else False

    def stop(self) -> None:
        self.cancelled = True
        if self._runner is not None:
            self._runner.cancel()

    # ---------------------------------------------------------------- parsing

    def _parse_line(self, line: str) -> Optional[dict]:
        match = _PROGRESS_RE.search(line)
        if not match:
            return None
        total = _parse_size(match.group("total") + (match.group("tunit") or "B"))
        speed = _parse_size(match.group("speed") + (match.group("sunit") or "B"))
        return {
            "percent": float(match.group("percent")),
            "downloaded": int(total * float(match.group("percent")) / 100.0) if total else 0,
            "total": total,
            "speed": speed,
            "eta": match.group("eta"),
            "message": line.strip(),
        }

    def classify_error(self, returncode: int, output: str) -> str:
        text = (output or "").lower()
        if any(token in text for token in ("private", "removed", "deleted", "blocked", "unavailable", "copyright")):
            return "fatal"
        return "transient"
