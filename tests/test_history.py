import json
from pathlib import Path

from universal_downloader import history


def test_append_and_read_all(tmp_paths, monkeypatch):
    target = tmp_paths / ".local/share/universal-downloader/history.jsonl"
    monkeypatch.setattr(history, "history_file", lambda: target)

    history.append("https://mega.nz/file/abc#secretKey", "mega", "File",
                   "/home/user/Videos/MEGA-abc", "ok")
    history.append("https://example.com/file.bin", "direct", "File", "", "failed")

    entries = history.read_all()
    assert len(entries) == 2
    assert entries[0]["source"] == "mega"
    assert entries[0]["status"] == "ok"
    assert "secretKey" not in entries[0]["url"]
    assert "<hidden>" in entries[0]["url"]
    assert entries[1]["status"] == "failed"


def test_last_status_and_destination(tmp_paths, monkeypatch):
    target = tmp_paths / ".local/share/universal-downloader/history.jsonl"
    monkeypatch.setattr(history, "history_file", lambda: target)

    assert history.last_status("https://example.com/x") is None
    history.append("https://example.com/x", "direct", "File", "/d1", "ok")
    history.append("https://example.com/x", "direct", "File", "/d2", "failed")
    assert history.last_status("https://example.com/x") == "failed"
    assert history.last_destination("https://example.com/x") == "/d2"


def test_is_completely_done(tmp_paths, monkeypatch):
    target = tmp_paths / ".local/share/universal-downloader/history.jsonl"
    monkeypatch.setattr(history, "history_file", lambda: target)

    # Not recorded -> not done.
    assert not history.is_completely_done("https://example.com/x")

    # Successful file with content -> done.
    history.append("https://example.com/x", "direct", "File", str(tmp_paths / "file.bin"), "ok")
    (tmp_paths / "file.bin").write_bytes(b"data")
    assert history.is_completely_done("https://example.com/x")

    # Empty file -> not done.
    (tmp_paths / "file.bin").write_bytes(b"")
    assert not history.is_completely_done("https://example.com/x")

    # Folder with completion marker and no partials -> done.
    folder = tmp_paths / "folder"
    folder.mkdir()
    (folder / "video.mkv").write_bytes(b"x")
    (folder / ".ud-complete").write_text("")
    history.append("https://example.com/f", "gdrive", "Folder", str(folder), "ok")
    assert history.is_completely_done("https://example.com/f")

    # Folder with a partial file -> not done.
    (folder / "episode.mkv.part").write_bytes(b"part")
    assert not history.is_completely_done("https://example.com/f")

    # --force overrides.
    assert history.is_completely_done("https://example.com/x", force=True) is False
