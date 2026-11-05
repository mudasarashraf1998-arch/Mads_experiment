"""Settings, history, logs and dependency-doctor dialogs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QBrush, QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from ..config import Settings
from ..backend.tools import probe_all
from ..paths import log_dir
from ..history import read_all, last_destination


FIELD_SPECS = [
    ("download_dir", "Download directory", "edit"),
    ("max_concurrent", "Max concurrent downloads", "spin", 1, 2),
    ("retries", "Retry attempts", "spin", 1, 20),
    ("retry_wait", "Seconds between retries", "spin", 0, 3600),
    ("yt_mode", "Default YouTube type", "combo", ["video", "audio"]),
    ("yt_quality", "Default YouTube quality", "combo",
     ["best", "2160", "1440", "1080", "720", "480", "360"]),
    ("yt_container", "Default container", "combo", ["mkv", "mp4"]),
    ("yt_audio", "Default audio quality", "combo",
     ["best", "mp3-320", "mp3-192", "mp3-128"]),
    ("yt_playlist", "Default YouTube playlist", "combo", ["single", "full"]),
    ("gdrive_cookies", "Drive cookies file (optional)", "edit"),
    ("direct_connections", "Direct connections per server", "spin", 1, 8),
    ("notifications", "Desktop notifications", "bool"),
    ("process_priority", "Process priority (nice)", "spin", -20, 20),
]


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, controller, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.controller = controller
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self.widgets = {}

        layout = QVBoxLayout(self)

        form = QFormLayout()
        for spec in FIELD_SPECS:
            key = spec[0]
            label = spec[1]
            kind = spec[2]
            current = self.settings.get(key)
            widget = self._build_field(kind, spec, current)
            if key == "download_dir":
                row = QHBoxLayout()
                row.addWidget(widget)
                browse = QPushButton("Browse…")
                browse.clicked.connect(self.browse_download_dir)
                row.addWidget(browse)
                wrapper = QWidget()
                wrapper.setLayout(row)
                form.addRow(label, wrapper)
            elif key == "gdrive_cookies":
                row = QHBoxLayout()
                row.addWidget(widget)
                browse = QPushButton("Browse…")
                browse.clicked.connect(self.browse_cookies)
                row.addWidget(browse)
                wrapper = QWidget()
                wrapper.setLayout(row)
                form.addRow(label, wrapper)
            else:
                form.addRow(label, widget)
            self.widgets[key] = widget

        layout.addLayout(form)

        hint = QLabel(
            "Personal data stays in your home directory: settings in "
            "~/.config/universal-downloader/, history and queue in "
            "~/.local/share/universal-downloader/, logs in "
            "~/.cache/universal-downloader/. Uninstalling never removes them."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8890a8; font-size: 12px;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_field(self, kind, spec, current):
        if kind == "edit":
            return QLineEdit(str(current))
        if kind == "spin":
            widget = QSpinBox()
            widget.setRange(spec[3], spec[4])
            widget.setValue(int(current))
            return widget
        if kind == "combo":
            widget = QComboBox()
            widget.addItems(spec[3])
            widget.setCurrentText(str(current))
            return widget
        if kind == "bool":
            widget = QCheckBox()
            widget.setChecked(str(current).lower() in ("1", "true", "yes", "on"))
            return widget
        return QLineEdit(str(current))

    def browse_download_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose download folder")
        if folder:
            self.widgets["download_dir"].setText(folder)

    def browse_cookies(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose cookies file")
        if path:
            self.widgets["gdrive_cookies"].setText(path)

    def save(self) -> None:
        for key, widget in self.widgets.items():
            if isinstance(widget, QLineEdit):
                self.settings.set(key, widget.text())
            elif isinstance(widget, QSpinBox):
                self.settings.set(key, widget.value())
            elif isinstance(widget, QComboBox):
                self.settings.set(key, widget.currentText())
            elif isinstance(widget, QCheckBox):
                self.settings.set(key, "true" if widget.isChecked() else "false")
        self.settings.save()
        self.controller.set_max_concurrent(int(self.settings.get("max_concurrent")))
        self.accept()


class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download history")
        self.resize(900, 400)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Source", "Type", "Link (redacted)", "Destination", "Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table)

        entries = read_all()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            for col, key in enumerate(["timestamp", "source", "type", "url", "destination", "status"]):
                self.table.setItem(row, col, QTableWidgetItem(str(entry.get(key, ""))))
        self.table.resizeColumnsToContents()

        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)


class LogsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Logs")
        self.resize(800, 500)
        layout = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.refresh = QPushButton("Refresh")
        self.refresh.clicked.connect(self.load_files)
        self.open_folder_btn = QPushButton("Open log folder")
        self.open_folder_btn.clicked.connect(self.open_folder)
        bar.addWidget(self.refresh)
        bar.addWidget(self.open_folder_btn)
        bar.addStretch()
        layout.addLayout(bar)

        self.file_list = QTableWidget(0, 3)
        self.file_list.setHorizontalHeaderLabels(["Log file", "Size", "Modified"])
        self.file_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.file_list.cellDoubleClicked.connect(self.load_selected)
        layout.addWidget(self.file_list)

        self.viewer = QTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setMaximumHeight(220)
        layout.addWidget(self.viewer)

        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

        self.load_files()

    def load_files(self) -> None:
        directory = log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        files = sorted(directory.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        self.file_list.setRowCount(len(files))
        for row, path in enumerate(files):
            stat = path.stat()
            self.file_list.setItem(row, 0, QTableWidgetItem(path.name))
            self.file_list.setItem(row, 1, QTableWidgetItem(self._human(stat.st_size)))
            self.file_list.setItem(
                row, 2, QTableWidgetItem(
                    datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                )
            )
        self.file_list.resizeColumnsToContents()

    @staticmethod
    def _human(num: int) -> str:
        units = ["B", "KB", "MB", "GB"]
        size = float(num)
        i = 0
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        return f"{size:.1f} {units[i]}" if i else f"{int(size)} B"

    def load_selected(self, row: int, column: int) -> None:
        name = self.file_list.item(row, 0).text()
        path = log_dir() / name
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.viewer.setPlainText(f"Could not read log: {exc}")
            return
        self.viewer.setPlainText(text)
        self.viewer.moveCursor(self.viewer.textCursor().End)

    def open_folder(self) -> None:
        directory = str(log_dir())
        Path(directory).mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(directory))


class DoctorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dependency doctor")
        self.resize(700, 420)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "The downloader detects external tools and works with whatever is "
            "installed. Missing required tools are shown with install hints."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #8890a8; font-size: 12px;")
        layout.addWidget(intro)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Tool", "For", "Status", "Version / hint"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.refresh()

        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    def refresh(self) -> None:
        tools = probe_all()
        rows = []
        for name, tool in tools.items():
            if tool.available:
                status = "Installed"
                detail = tool.version or ""
            else:
                status = "Required" if tool.required else "Optional"
                detail = tool.hint or ""
            rows.append((name, tool.purpose, status, detail))
        rows.sort(key=lambda r: (0 if r[2] == "Installed" else 1, r[0]))
        self.table.setRowCount(len(rows))
        for row, (name, purpose, status, detail) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(purpose))
            status_item = QTableWidgetItem(status)
            if status == "Installed":
                status_item.setForeground(QBrush(QColor("#00d97a")))
            else:
                status_item.setForeground(QBrush(QColor("#ff5c66")))
            self.table.setItem(row, 2, status_item)
            self.table.setItem(row, 3, QTableWidgetItem(detail))
        self.table.resizeColumnsToContents()
