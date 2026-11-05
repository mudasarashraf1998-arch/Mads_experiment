import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def tmp_paths(monkeypatch, tmp_path):
    """Redirect XDG locations to a temporary directory."""
    root = tmp_path / "ud"
    (root / ".config" / "universal-downloader").mkdir(parents=True)
    (root / ".local" / "share" / "universal-downloader").mkdir(parents=True)
    (root / ".cache" / "universal-downloader" / "logs").mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(root / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(root / ".local/share"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(root / ".cache"))
    return root


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
