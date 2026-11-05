"""Persistent download queue.

Queue items are serialised to ~/.local/share/universal-downloader/queue.json.
State machine:

    Waiting -> Downloading -> Paused  (pause/resume where supported)
                -> Completed / Failed / Cancelled

A Failed item can be retried (returns to Waiting) and a Completed item can be
removed from the list while its files stay where they are.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .paths import queue_file

STATES = ("waiting", "detecting", "downloading", "paused", "completed", "failed", "cancelled")

VALID_TRANSITIONS = {
    "waiting": {"downloading", "cancelled", "failed"},
    "detecting": {"downloading", "waiting", "failed", "cancelled"},
    "downloading": {"paused", "completed", "failed", "cancelled"},
    "paused": {"downloading", "cancelled", "failed"},
    "completed": {"cancelled"},        # remove-completed keeps the record
    "failed": {"waiting", "cancelled"},  # retry
    "cancelled": set(),
}


@dataclass
class QueueItem:
    id: str
    url: str
    source: str
    kind: str
    title: str
    destination: str
    options: dict[str, Any] = field(default_factory=dict)
    state: str = "waiting"
    progress: float = 0.0
    downloaded: int = 0
    total: int = 0
    speed: float = 0.0
    eta: str = ""
    status_message: str = ""
    attempts: int = 0
    max_attempts: int = 5
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: str = ""
    skip_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueueItem":
        defaults = {f.name: f.default for f in cls.__dataclass_fields__.values()}
        merged = dict(defaults)
        merged.update(data)
        return cls(**merged)

    def touch(self) -> None:
        self.updated_at = time.time()


class QueueModel:
    """Thread-safe queue with on-disk persistence."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else queue_file()
        self.lock = threading.RLock()
        self.items: list[QueueItem] = []
        self._callbacks: list = []
        self.load()

    # ---------------------------------------------------------------- persistence

    def load(self) -> None:
        with self.lock:
            if not self.path.exists():
                self.items = []
                return
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.items = []
                return
            self.items = [QueueItem.from_dict(entry) for entry in data]
            # Recoverable states: a download interrupted by a crash goes back
            # to waiting so the backend resume logic can pick it up.
            for item in self.items:
                if item.state in ("downloading", "paused"):
                    item.state = "waiting"
                    item.progress = 0.0

    def save(self) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(
                [item.to_dict() for item in self.items],
                indent=2,
                ensure_ascii=False,
            )
            self.path.write_text(payload, encoding="utf-8")

    # ---------------------------------------------------------------- observers

    def on_change(self, callback) -> None:
        self._callbacks.append(callback)

    def _notify(self) -> None:
        for callback in self._callbacks:
            try:
                callback()
            except Exception:
                pass

    # ---------------------------------------------------------------- commands

    def add(self, item: QueueItem) -> QueueItem:
        with self.lock:
            item.id = item.id or str(uuid.uuid4())
            item.created_at = time.time()
            item.updated_at = item.created_at
            self.items.append(item)
            self.save()
        self._notify()
        return item

    def get(self, item_id: str) -> QueueItem | None:
        with self.lock:
            for item in self.items:
                if item.id == item_id:
                    return item
        return None

    def list_items(self) -> list[QueueItem]:
        with self.lock:
            return list(self.items)

    def set_state(self, item_id: str, state: str) -> bool:
        if state not in STATES:
            return False
        with self.lock:
            item = self._find_locked(item_id)
            if not item:
                return False
            if state != item.state and state not in VALID_TRANSITIONS.get(item.state, set()):
                # Same-state transitions are always allowed.
                if state != item.state:
                    return False
            item.state = state
            item.touch()
            self.save()
        self._notify()
        return True

    def update_progress(
        self,
        item_id: str,
        *,
        progress: float | None = None,
        downloaded: int | None = None,
        total: int | None = None,
        speed: float | None = None,
        eta: str | None = None,
        status_message: str | None = None,
        state: str | None = None,
        error: str | None = None,
        attempts: int | None = None,
    ) -> bool:
        with self.lock:
            item = self._find_locked(item_id)
            if not item:
                return False
            if progress is not None:
                item.progress = max(0.0, min(100.0, progress))
            if downloaded is not None:
                item.downloaded = downloaded
            if total is not None:
                item.total = total
            if speed is not None:
                item.speed = speed
            if eta is not None:
                item.eta = eta
            if status_message is not None:
                item.status_message = status_message
            if state is not None:
                if state != item.state and state not in VALID_TRANSITIONS.get(item.state, set()):
                    return False
                item.state = state
            if error is not None:
                item.error = error
            if attempts is not None:
                item.attempts = attempts
            item.touch()
            self.save()
        self._notify()
        return True

    def increment_attempts(self, item_id: str) -> int:
        with self.lock:
            item = self._find_locked(item_id)
            if not item:
                return 0
            item.attempts += 1
            item.touch()
            count = item.attempts
            self.save()
        self._notify()
        return count

    def remove(self, item_id: str) -> bool:
        with self.lock:
            for index, item in enumerate(self.items):
                if item.id == item_id:
                    self.items.pop(index)
                    self.save()
                    self._notify()
                    return True
        return False

    def clear_completed(self) -> int:
        with self.lock:
            before = len(self.items)
            self.items = [item for item in self.items if item.state != "completed"]
            removed = before - len(self.items)
            self.save()
        self._notify()
        return removed

    # ---------------------------------------------------------------- internals

    def _find_locked(self, item_id: str) -> QueueItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None
