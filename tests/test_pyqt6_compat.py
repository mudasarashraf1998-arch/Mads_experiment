"""PyQt6 compatibility tests.

These tests verify that all PyQt6 imports and API usage across the
application are correct for PyQt6 6.x. They test the QtCore module
(which is importable without a display) and check the QtGui/QtWidgets
stub files to confirm class locations.

Note: QtGui and QtWidgets cannot be imported in this headless sandbox
because libxkbcommon.so.0 is missing. On Linux Mint 22.3, python3-pyqt6
pulls in libxkbcommon0 automatically, so these imports work there.
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest

# ------------------------------------------------------------------ QtCore imports (importable in sandbox)

QTCORE_CLASSES = [
    "Qt",
    "QUrl",
    "QObject",
    "QThreadPool",
    "QTimer",
    "QRunnable",
    "pyqtSignal",
    "pyqtSlot",
    "QLocale",
]


def test_qtcore_imports() -> None:
    """Every QtCore class used by the app must be importable from PyQt6.QtCore."""
    from PyQt6.QtCore import (  # noqa: F401
        Qt, QUrl, QObject, QThreadPool, QTimer, QRunnable,
        pyqtSignal, pyqtSlot, QLocale,
    )


def test_qlocale_enum_api() -> None:
    """QLocale must use PyQt6 enum classes (Language/Country), not flat enums."""
    from PyQt6.QtCore import QLocale

    # Flat enum access (PyQt5 style) must NOT exist
    assert not hasattr(QLocale, "English"), "QLocale.English is PyQt5 style"
    assert not hasattr(QLocale, "UnitedKingdom"), "QLocale.UnitedKingdom is PyQt5 style"

    # PyQt6 enum classes must exist
    assert hasattr(QLocale, "Language"), "QLocale.Language missing"
    assert hasattr(QLocale, "Country"), "QLocale.Country missing"

    # Construction must work
    loc = QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom)
    assert loc is not None


def test_pyqt_slot_decorator() -> None:
    """pyqtSlot must work as a decorator with typed arguments."""
    from PyQt6.QtCore import pyqtSlot

    class _Obj:
        @pyqtSlot(str, dict)
        def _method(self, a: str, b: dict) -> None:
            pass

    assert _Obj._method is not None


# ------------------------------------------------------------------ QtGui class location (via stub files)

QTGUI_CLASSES = ["QColor", "QBrush", "QPalette", "QDesktopServices", "QIcon"]


def test_qtgui_class_locations() -> None:
    """Every QtGui class used by the app must be defined in PyQt6.QtGui stubs."""
    stub = Path(
        "/usr/local/lib/python3.11/dist-packages/PyQt6/QtGui.pyi"
    )
    assert stub.exists(), f"QtGui stub not found at {stub}"
    content = stub.read_text()
    for cls in QTGUI_CLASSES:
        assert re.search(rf"class {cls}\b", content), f"{cls} not found in QtGui stub"

    # QPalette.ColorRole must exist
    assert "class ColorRole" in content, "QPalette.ColorRole not found in QtGui stub"


# ------------------------------------------------------------------ QtWidgets class location (via stub files)

QTWIDGETS_CLASSES = [
    "QApplication", "QAbstractItemView", "QHeaderView", "QDialogButtonBox",
    "QFrame", "QHBoxLayout", "QLabel", "QLineEdit", "QMainWindow",
    "QMessageBox", "QPushButton", "QTableWidget", "QTableWidgetItem",
    "QVBoxLayout", "QWidget", "QProgressBar", "QCheckBox", "QComboBox",
    "QDialog", "QFileDialog", "QFormLayout", "QGroupBox", "QGridLayout",
    "QRadioButton", "QScrollArea", "QSizePolicy", "QStackedWidget",
    "QButtonGroup", "QTextEdit", "QSpinBox",
]


def test_qtwidgets_class_locations() -> None:
    """Every QtWidgets class used by the app must be defined in PyQt6.QtWidgets stubs."""
    stub = Path(
        "/usr/local/lib/python3.11/dist-packages/PyQt6/QtWidgets.pyi"
    )
    assert stub.exists(), f"QtWidgets stub not found at {stub}"
    content = stub.read_text()
    for cls in QTWIDGETS_CLASSES:
        assert re.search(rf"class {cls}\b", content), f"{cls} not found in QtWidgets stub"

    # Enum sub-classes
    assert "class SelectionBehavior" in content, "QAbstractItemView.SelectionBehavior missing"
    assert "class EditTrigger" in content, "QAbstractItemView.EditTrigger missing"
    assert "class ResizeMode" in content, "QHeaderView.ResizeMode missing"
    assert "class StandardButton" in content, "QDialogButtonBox.StandardButton missing"


# ------------------------------------------------------------------ Module import tests

APP_MODULES = [
    "universal_downloader.gui.app",
    "universal_downloader.gui.widgets",
    "universal_downloader.jobs",
]


def test_app_module_imports() -> None:
    """Non-widget GUI modules must import successfully."""
    # QtWidgets-dependent modules may fail in headless sandbox (missing libxkbcommon.so.0).
    # On Linux Mint 22.3 with python3-pyqt6 installed, these all import fine.
    for mod_name in APP_MODULES:
        try:
            importlib.import_module(mod_name)
        except ImportError as exc:
            if "libxkbcommon" in str(exc):
                pytest.skip(f"{mod_name} skipped: QtWidgets not importable in headless sandbox")
            raise


def test_window_imports_qtcore_only() -> None:
    """gui/window.py must only import QtCore classes that are in QtCore."""
    import ast
    import sys

    src = Path("universal_downloader/gui/window.py").read_text()
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "PyQt6.QtCore":
            names = {alias.name for alias in node.names}
            allowed = {"Qt", "QUrl"}
            extra = names - allowed
            assert not extra, f"window.py imports non-QtCore classes from QtCore: {extra}"


def test_dialogs_imports_qtcore_only() -> None:
    """gui/dialogs.py must only import QtCore classes that are in QtCore."""
    import ast

    src = Path("universal_downloader/gui/dialogs.py").read_text()
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "PyQt6.QtCore":
            names = {alias.name for alias in node.names}
            allowed = {"QUrl", "Qt"}
            extra = names - allowed
            assert not extra, f"dialogs.py imports non-QtCore classes from QtCore: {extra}"


def test_widgets_imports_qtcore_only() -> None:
    """gui/widgets.py must only import QtCore classes that are in QtCore."""
    import ast

    src = Path("universal_downloader/gui/widgets.py").read_text()
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "PyQt6.QtCore":
            names = {alias.name for alias in node.names}
            allowed = {"Qt", "pyqtSignal"}
            extra = names - allowed
            assert not extra, f"widgets.py imports non-QtCore classes from QtCore: {extra}"


def test_jobs_imports_qtcore_only() -> None:
    """jobs.py must only import QtCore classes that are in QtCore."""
    import ast

    src = Path("universal_downloader/jobs.py").read_text()
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "PyQt6.QtCore":
            names = {alias.name for alias in node.names}
            allowed = {"QObject", "QThreadPool", "QTimer", "QRunnable", "pyqtSignal", "pyqtSlot"}
            extra = names - allowed
            assert not extra, f"jobs.py imports non-QtCore classes from QtCore: {extra}"


def test_app_imports_qtcore_only() -> None:
    """gui/app.py must only import QtCore classes that are in QtCore."""
    import ast

    src = Path("universal_downloader/gui/app.py").read_text()
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "PyQt6.QtCore":
            names = {alias.name for alias in node.names}
            allowed = {"QLocale"}
            extra = names - allowed
            assert not extra, f"app.py imports non-QtCore classes from QtCore: {extra}"


def test_job_controller_init_no_nameerror(tmp_path) -> None:
    """JobController.__init__ must not raise NameError for undefined 'model'.

    Regression test: `model.on_change(...)` was used instead of
    `self.model.on_change(...)` in JobController.__init__, causing a
    NameError crash at GUI startup on systems where QtWidgets imports
    succeed (e.g. Linux Mint 22.3 with python3-pyqt6).
    """
    from universal_downloader.config import Settings
    from universal_downloader.jobs import JobController
    from universal_downloader.queue import QueueModel

    model = QueueModel(tmp_path / "queue.json")
    settings = Settings()
    controller = JobController(model, settings)
    assert controller.model is model


def test_no_qt5_style_locale() -> None:
    """No source file should use PyQt5-style QLocale flat enums."""
    import ast

    py_files = [
        "universal_downloader/gui/app.py",
        "universal_downloader/gui/window.py",
        "universal_downloader/gui/dialogs.py",
        "universal_downloader/gui/widgets.py",
        "universal_downloader/jobs.py",
    ]
    for fpath in py_files:
        src = Path(fpath).read_text()
        assert "QLocale.English" not in src, f"{fpath} uses PyQt5-style QLocale.English"
        assert "QLocale.UnitedKingdom" not in src, f"{fpath} uses PyQt5-style QLocale.UnitedKingdom"


def test_no_clipboard_mode() -> None:
    """No source file should use QApplication.ClipboardMode (PyQt6 removed it)."""
    import ast

    py_files = [
        "universal_downloader/gui/app.py",
        "universal_downloader/gui/window.py",
        "universal_downloader/gui/dialogs.py",
        "universal_downloader/gui/widgets.py",
        "universal_downloader/jobs.py",
    ]
    for fpath in py_files:
        src = Path(fpath).read_text()
        assert "ClipboardMode" not in src, f"{fpath} uses removed QApplication.ClipboardMode"


# ------------------------------------------------------------------ GUI import completeness

GUI_FILES = [
    "universal_downloader/gui/app.py",
    "universal_downloader/gui/window.py",
    "universal_downloader/gui/dialogs.py",
    "universal_downloader/gui/widgets.py",
]

# Known non-Qt names starting with Q that are imported from local modules,
# not PyQt6. These should be excluded from the Qt import check.
NON_QT_Q_NAMES = {"QueueItem", "QueueModel"}


def _qt_class_usages(src: str) -> set[str]:
    """Return Qt class names referenced in source (Q-prefixed names used as calls/types)."""
    tree = ast.parse(src)
    usages: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id.startswith("Q") and len(node.id) > 1:
            usages.add(node.id)
        # Also catch attribute-style like Qt.AlignmentFlag (already handled by module check)
    return usages


def _qt_imports(src: str) -> dict[str, set[str]]:
    """Return {module: set of imported names} for PyQt6 imports."""
    tree = ast.parse(src)
    imports: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("PyQt6."):
            names = {alias.name for alias in node.names}
            imports.setdefault(node.module, set()).update(names)
    return imports


def test_all_qt_classes_imported_in_gui_files() -> None:
    """Every Q-prefixed Qt class used in GUI files must be imported from PyQt6.

    Regression test: QComboBox and QGroupBox were used in gui/window.py but
    not imported, causing NameError at GUI startup on Linux Mint 22.3.
    QLineEdit was used in gui/dialogs.py but not imported.
    """
    import ast

    for fpath in GUI_FILES:
        src = Path(fpath).read_text()
        usages = _qt_class_usages(src)
        imports = _qt_imports(src)

        all_imported: set[str] = set()
        for names in imports.values():
            all_imported.update(names)

        # Remove non-Qt local names
        usages = usages - NON_QT_Q_NAMES

        missing = usages - all_imported
        assert not missing, (
            f"{fpath}: Qt classes used but not imported: {sorted(missing)}. "
            f"Add them to the PyQt6 import statement."
        )


def test_gui_modules_importable() -> None:
    """All GUI modules must import without NameError or ImportError.

    Skips in headless sandbox when PyQt6.QtWidgets cannot be imported
    due to missing libxkbcommon.so.0. On Linux Mint 22.3, all import fine.
    """
    import importlib

    mod_names = [
        "universal_downloader.gui.app",
        "universal_downloader.gui.widgets",
        "universal_downloader.gui.dialogs",
        "universal_downloader.gui.window",
    ]
    for mod_name in mod_names:
        try:
            importlib.import_module(mod_name)
        except ImportError as exc:
            if "libxkbcommon" in str(exc):
                pytest.skip(f"{mod_name} skipped: QtWidgets not importable in headless sandbox")
            raise


def test_main_window_construction() -> None:
    """MainWindow must construct without NameError.

    Skips in headless sandbox when PyQt6.QtWidgets cannot be imported
    due to missing libxkbcommon.so.0. On Linux Mint 22.3, this constructs
    the full window including QComboBox, QGroupBox, etc.
    """
    try:
        from universal_downloader.gui.window import MainWindow
    except ImportError as exc:
        if "libxkbcommon" in str(exc):
            pytest.skip("MainWindow skipped: QtWidgets not importable in headless sandbox")
        raise
    from universal_downloader.config import Settings

    settings = Settings()
    window = MainWindow()
    assert window is not None
    assert window.model is not None
    assert window.controller is not None
    # Verify the previously-missing widgets exist
    assert hasattr(window, "source_combo"), "source_combo (QComboBox) not created"
    assert hasattr(window, "options_box"), "options_box (QGroupBox) not created"
    window.close()
