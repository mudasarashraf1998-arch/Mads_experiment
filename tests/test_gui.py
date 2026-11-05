"""GUI tests.

These require PyQt6 and a working Qt platform plugin, which may not be
available in a headless build environment. They are skipped in that case.
"""

import pytest

try:
    from PyQt6.QtWidgets import QApplication  # noqa: F401
    HAS_QT = True
except Exception:  # missing platform libraries in this sandbox
    HAS_QT = False

skip_no_qt = pytest.mark.skipif(not HAS_QT, reason="PyQt6/Qt platform not available")


@skip_no_qt
def test_options_stack_switches_sources():
    from universal_downloader.gui.widgets import OptionsStack
    stack = OptionsStack()
    stack.show_source("youtube")
    stack.show_source("direct")
    opts = stack.options()
    assert "direct_connections" in opts


@skip_no_qt
def test_main_window_creates(qapp):
    from universal_downloader.gui.window import MainWindow
    win = MainWindow()
    assert win is not None
    win.close()


@skip_no_qt
def test_add_url_creates_queue_row(qapp):
    from universal_downloader.gui.window import MainWindow
    win = MainWindow()
    win.url_entry.setText("https://youtu.be/dQw4w")
    win.source_combo.setCurrentText("YouTube")
    win.on_add()
    assert len(win.model.list_items()) == 1
    item = win.model.list_items()[0]
    assert item.source == "youtube"
    win.close()
