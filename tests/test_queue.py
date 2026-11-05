import json
from pathlib import Path

from universal_downloader.queue import QueueItem, QueueModel, VALID_TRANSITIONS


def test_add_and_persist(tmp_path):
    qfile = tmp_path / "queue.json"
    model = QueueModel(qfile)
    item = QueueItem(
        id="", url="https://example.com/file.bin", source="direct", kind="File",
        title="file.bin", destination="/tmp/dest", state="waiting",
    )
    model.add(item)
    assert item.id
    saved = json.loads(qfile.read_text())
    assert len(saved) == 1
    assert saved[0]["state"] == "waiting"

    # Reload keeps data.
    model2 = QueueModel(qfile)
    assert len(model2.list_items()) == 1
    assert model2.list_items()[0].id == item.id


def test_state_transitions(tmp_path):
    model = QueueModel(tmp_path / "queue.json")
    item = model.add(QueueItem(id="1", url="u", source="direct", kind="File",
                               title="t", destination="/tmp/d", state="waiting"))
    assert model.set_state(item.id, "downloading") is True
    assert model.set_state(item.id, "paused") is True
    assert model.set_state(item.id, "downloading") is True
    assert model.set_state(item.id, "completed") is True
    # Going backwards from completed is not allowed.
    assert model.set_state(item.id, "downloading") is False
    assert model.get(item.id).state == "completed"


def test_failed_retry_transition(tmp_path):
    model = QueueModel(tmp_path / "queue.json")
    item = model.add(QueueItem(id="1", url="u", source="direct", kind="File",
                               title="t", destination="/tmp/d", state="failed"))
    assert model.set_state(item.id, "waiting") is True


def test_clear_completed(tmp_path):
    qfile = tmp_path / "queue.json"
    model = QueueModel(qfile)
    model.add(QueueItem(id="1", url="u1", source="direct", kind="File",
                        title="t1", destination="/tmp/d", state="completed"))
    model.add(QueueItem(id="2", url="u2", source="direct", kind="File",
                        title="t2", destination="/tmp/d", state="failed"))
    assert model.clear_completed() == 1
    assert len(model.list_items()) == 1
    assert model.list_items()[0].state == "failed"
