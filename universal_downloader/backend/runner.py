"""Subprocess runner for download backends.

Design goals for the target computer:

* No file is ever loaded entirely into RAM: output is read line by line.
* No busy polling: reader threads block on the pipe.
* Progress is parsed from real tool output, never simulated.
* Pause/resume uses SIGSTOP/SIGCONT where the underlying tool survives it.
* Cancel kills the whole process group so no orphan is left behind.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

OutputLine = Callable[[str], None]
ProgressUpdate = Callable[[dict], None]


@dataclass
class ProcessResult:
    returncode: int
    state: str  # "completed", "failed", "cancelled", "paused"
    error: str = ""


class SubprocessRunner:
    def __init__(
        self,
        cmd: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        on_output: OutputLine | None = None,
        on_progress: ProgressUpdate | None = None,
        parse_line: Callable[[str], Optional[dict]] | None = None,
        kill_children: bool = True,
    ) -> None:
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self.on_output = on_output
        self.on_progress = on_progress
        self.parse_line = parse_line
        self.kill_children = kill_children

        self._proc: Optional[subprocess.Popen] = None
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._cancelled = False
        self._paused = False
        self._returncode: Optional[int] = None
        self._last_emit = 0.0

    # ------------------------------------------------------------------ start

    def start(self) -> None:
        full_env = os.environ.copy()
        if self.env:
            full_env.update(self.env)
        # Its own process group so cancel can kill every child tool too.
        self._proc = subprocess.Popen(
            self.cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            cwd=self.cwd,
            env=full_env,
            bufsize=0,
            preexec_fn=os.setsid if self.kill_children else None,
        )
        self._threads = [
            threading.Thread(target=self._pump, args=(self._proc.stdout, "stdout"), daemon=True),
            threading.Thread(target=self._pump, args=(self._proc.stderr, "stderr"), daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def _pump(self, stream, stream_name: str) -> None:
        assert self._proc is not None and stream is not None
        while True:
            data = stream.readline()
            if not data:
                break
            try:
                line = data.decode("utf-8", errors="replace").rstrip("\r\n")
            except Exception:
                continue
            if not line:
                continue
            if self.on_output:
                self.on_output(f"[{stream_name}] {line}")
            if self.parse_line and self.on_progress:
                update = self.parse_line(line)
                if update:
                    self._emit_progress(update)

    def _emit_progress(self, update: dict) -> None:
        import time

        now = time.monotonic()
        # Throttle progress updates: the GUI does not need more than a few
        # updates per second, and throttling keeps the old CPU idle.
        if now - self._last_emit < 0.25 and not update.get("force"):
            return
        self._last_emit = now
        if self.on_progress:
            self.on_progress(update)

    # ------------------------------------------------------------------ control

    def pause(self) -> bool:
        with self._lock:
            if not self._proc or self._paused or self._cancelled:
                return False
            pid = self._proc.pid
            if pid is None:
                return False
        try:
            if self.kill_children:
                os.killpg(pid, signal.SIGSTOP)
            else:
                os.kill(pid, signal.SIGSTOP)
            self._paused = True
            return True
        except (ProcessLookupError, PermissionError, OSError):
            return False

    def resume(self) -> bool:
        with self._lock:
            if not self._proc or not self._paused or self._cancelled:
                return False
            pid = self._proc.pid
            if pid is None:
                return False
        try:
            if self.kill_children:
                os.killpg(pid, signal.SIGCONT)
            else:
                os.kill(pid, signal.SIGCONT)
            self._paused = False
            return True
        except (ProcessLookupError, PermissionError, OSError):
            return False

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            proc = self._proc
        if proc is None:
            return
        try:
            if self.kill_children and proc.pid is not None:
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def wait(self) -> ProcessResult:
        assert self._proc is not None
        try:
            self._proc.wait()
        except KeyboardInterrupt:
            self.cancel()
            self._proc.wait()
        with self._lock:
            rc = self._proc.returncode
            self._returncode = rc
            cancelled = self._cancelled
            paused = self._paused
        if cancelled:
            state = "cancelled"
        elif paused:
            state = "paused"
        elif rc == 0:
            state = "completed"
        else:
            state = "failed"
        return ProcessResult(returncode=rc or -1, state=state)

    @property
    def pid(self) -> Optional[int]:
        with self._lock:
            return self._proc.pid if self._proc else None

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    @property
    def process(self):
        return self._proc

    def poll(self):
        return self._proc.poll() if self._proc else None
