"""Download job controller: concurrency, retries, state transitions.

Backend adapters run in the application thread pool. Every Qt signal emitted
by a job is delivered to the GUI thread (queued delivery), so the model and
the interface are only ever touched from the GUI thread.
"""

from __future__ import annotations

import threading
from typing import Optional

from PyQt6.QtCore import QObject, QThreadPool, QTimer, QRunnable, pyqtSignal, pyqtSlot

from .queue import QueueItem, QueueModel, STATES
from .backend.adapter import DownloadOptions, AdapterResult
from .backend.youtube import YouTubeAdapter
from .backend.gdrive import GDriveAdapter
from .backend.mega import MegaAdapter
from .backend.direct import DirectAdapter
from .config import Settings
from .history import append as history_append
from .logging_ import info, warn, error
from .utils import redact

ADAPTERS = {
    "youtube": YouTubeAdapter,
    "gdrive": GDriveAdapter,
    "mega": MegaAdapter,
    "direct": DirectAdapter,
}

TRANSIENT_ERROR_TOKENS = ("network", "timed out", "connection", "temporary",
                          "try again", "unavailable server", "502", "503", "429")
FATAL_ERROR_TOKENS = ("quota", "rate limit", "permission", "access denied", "not found",
                      "404", "private", "removed", "deleted", "blocked", "unavailable",
                      "not installed", "invalid", "bad link", "no videos", "no completed files")


class JobSignals(QObject):
    progress = pyqtSignal(str, dict)   # item_id, update
    state = pyqtSignal(str, str)       # item_id, new state
    finished = pyqtSignal(str, dict)   # item_id, result
    log = pyqtSignal(str, str)         # item_id, line


class _Task(QRunnable):
    """Wraps a callable for QThreadPool."""

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.setAutoDelete(True)

    def run(self) -> None:
        self.fn()


class DownloadJob(QObject):
    """Executes one queue item's adapter in a worker thread."""

    def __init__(self, item: QueueItem, settings: Settings):
        super().__init__()
        self.item = item
        self.settings = settings
        self.signals = JobSignals()
        self.adapter = self._build_adapter(item)
        self._cancelled = False

    def _build_adapter(self, item: QueueItem):
        cls = ADAPTERS.get(item.source)
        if cls is None:
            raise ValueError(f"Unknown source: {item.source}")
        extra = dict(item.options)
        extra["url"] = item.url
        extra["retries"] = self.settings.getint("retries")
        extra["retry_wait"] = self.settings.getint("retry_wait")
        if item.source == "direct":
            extra["direct_connections"] = self.settings.getint("direct_connections")
        options = DownloadOptions(
            source=item.source,
            destination=item.destination,
            title=item.title,
            extra=extra,
        )
        return cls(options)

    def pause(self) -> bool:
        runner = getattr(self.adapter, "_runner", None)
        if runner is not None and hasattr(runner, "pause"):
            return runner.pause()
        return False

    def resume(self) -> bool:
        runner = getattr(self.adapter, "_runner", None)
        if runner is not None and hasattr(runner, "resume"):
            return runner.resume()
        return False

    def cancel(self) -> None:
        self._cancelled = True
        self.adapter.stop()

    def run(self) -> AdapterResult:
        item_id = self.item.id

        def on_progress(update: dict) -> None:
            if self._cancelled:
                return
            self.signals.progress.emit(item_id, update)

        def on_output(line: str) -> None:
            self.signals.log.emit(item_id, line)

        try:
            result = self.adapter.run(on_progress=on_progress, on_output=on_output)
        except Exception as exc:  # noqa: BLE001
            error("job crashed", f"{item_id}: {exc}")
            result = AdapterResult(state="failed", error=str(exc))
        self.signals.finished.emit(item_id, result)
        return result

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class JobController(QObject):
    """Owns queue execution: starts jobs, enforces concurrency, schedules retries."""

    jobProgress = pyqtSignal(str, dict)
    jobState = pyqtSignal(str, str)
    jobFinished = pyqtSignal(str, dict)
    jobLog = pyqtSignal(str, str)

    def __init__(self, queue_model: QueueModel, settings: Settings, parent=None):
        super().__init__(parent)
        self.model = queue_model
        self.settings = settings
        self.pool = QThreadPool.globalInstance()
        self.active: dict[str, DownloadJob] = {}
        self._lock = threading.Lock()
        self._retry_timers: dict[str, QTimer] = {}
        self.model.on_change(self._refresh_concurrency)

    # ---------------------------------------------------------------- public API

    def max_concurrent(self) -> int:
        return max(1, min(2, self.settings.getint("max_concurrent")))

    def set_max_concurrent(self, value: int) -> None:
        self.settings.set("max_concurrent", str(max(1, min(2, int(value)))))
        self.settings.save()
        self._refresh_concurrency()

    def add(self, item: QueueItem) -> None:
        self.model.add(item)
        self._refresh_concurrency()

    def is_active(self, item_id: str) -> bool:
        with self._lock:
            return item_id in self.active

    def _refresh_concurrency(self) -> None:
        with self._lock:
            running = len(self.active)
        while running < self.max_concurrent():
            item = self._next_waiting()
            if item is None:
                break
            self._launch(item)
            running += 1

    def _next_waiting(self) -> Optional[QueueItem]:
        for item in self.model.list_items():
            if item.state == "waiting":
                return item
        return None

    def _launch(self, item: QueueItem) -> None:
        job = DownloadJob(item, self.settings)
        job.signals.progress.connect(self._on_progress)
        job.signals.state.connect(self._on_state)
        job.signals.finished.connect(self._on_finished)
        job.signals.log.connect(self._on_log)
        with self._lock:
            self.active[item.id] = job
        self.model.set_state(item.id, "downloading")
        info("job started", f"{item.source}: {redact(item.url)}")
        self.pool.start(_Task(job.run))

    # ---------------------------------------------------------------- signal slots (GUI thread)

    @pyqtSlot(str, dict)
    def _on_progress(self, item_id: str, update: dict) -> None:
        self.model.update_progress(
            item_id,
            progress=update.get("percent"),
            downloaded=update.get("downloaded"),
            total=update.get("total"),
            speed=update.get("speed"),
            eta=update.get("eta"),
            status_message=update.get("message"),
        )
        self.jobProgress.emit(item_id, update)

    @pyqtSlot(str, str)
    def _on_state(self, item_id: str, state: str) -> None:
        self.model.set_state(item_id, state)
        self.jobState.emit(item_id, state)

    @pyqtSlot(str, dict)
    def _on_finished(self, item_id: str, result: dict) -> None:
        self._deliver_result(item_id, result)

    @pyqtSlot(str, str)
    def _on_log(self, item_id: str, line: str) -> None:
        self.jobLog.emit(item_id, line)

    def _deliver_result(self, item_id: str, result: AdapterResult) -> None:
        item = self.model.get(item_id)
        if item is None:
            return
        with self._lock:
            self.active.pop(item_id, None)

        if result.state == "cancelled":
            self.model.set_state(item_id, "cancelled", error=result.error)
            self.jobFinished.emit(item_id, {"state": "cancelled", "error": result.error})
            self._refresh_concurrency()
            return

        if result.state == "completed":
            self.model.set_state(
                item_id, "completed",
                progress=100.0, downloaded=result.size or 0, total=result.size or 0,
                status_message=f"{result.files} file(s) saved",
            )
            history_append(item.url, item.source, item.kind, result.destination, "ok")
            self.jobFinished.emit(item_id, {"state": "completed", "destination": result.destination})
            self._refresh_concurrency()
            return

        # Failed: retry automatically when the error looks transient.
        attempts = self.model.increment_attempts(item_id)
        max_attempts = item.max_attempts
        if self._is_transient(result.error) and attempts < max_attempts:
            wait = self.settings.getint("retry_wait")
            self.model.set_state(item_id, "waiting", error=result.error)
            warn("retry scheduled", f"{item_id}: attempt {attempts}/{max_attempts} in {wait}s")
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda checked=False, iid=item_id: self._retry(iid))
            self._retry_timers[item_id] = timer
            timer.start(wait * 1000)
            self.jobFinished.emit(item_id, {"state": "retrying", "error": result.error})
        else:
            self.model.set_state(item_id, "failed", error=result.error)
            history_append(item.url, item.source, item.kind, item.destination, "failed")
            self.jobFinished.emit(item_id, {"state": "failed", "error": result.error})
        self._refresh_concurrency()

    def _retry(self, item_id: str) -> None:
        self._retry_timers.pop(item_id, None)
        item = self.model.get(item_id)
        if item is None:
            return
        self.model.set_state(item_id, "waiting", error="")
        self._refresh_concurrency()

    def _is_transient(self, error: str) -> bool:
        text = (error or "").lower()
        if any(token in text for token in FATAL_ERROR_TOKENS):
            return False
        if any(token in text for token in TRANSIENT_ERROR_TOKENS):
            return True
        # Unknown errors: retry, since we cannot prove they are permanent.
        return True

    # ---------------------------------------------------------------- user actions

    def pause_job(self, item_id: str) -> bool:
        with self._lock:
            job = self.active.get(item_id)
        if job and job.pause():
            self.model.set_state(item_id, "paused")
            return True
        return False

    def resume_job(self, item_id: str) -> bool:
        with self._lock:
            job = self.active.get(item_id)
        if job and job.resume():
            self.model.set_state(item_id, "downloading")
            return True
        return False

    def cancel_job(self, item_id: str) -> bool:
        with self._lock:
            job = self.active.get(item_id)
        if job:
            job.cancel()
            self.model.set_state(item_id, "cancelled")
            return True
        return False

    def retry_job(self, item_id: str) -> None:
        item = self.model.get(item_id)
        if item and item.state in ("failed", "cancelled"):
            self.model.set_state(item_id, "waiting", error="", attempts=0)
            self._refresh_concurrency()

    def remove_job(self, item_id: str) -> None:
        self.cancel_job(item_id)
        self.model.remove(item_id)
