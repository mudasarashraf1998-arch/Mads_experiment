"""Main application window.

Single polished view: link bar, source-specific options, download queue and a
bottom action bar. Optimised for 1366x768 and kept deliberately uncluttered.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QColor, QBrush
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QProgressBar,
)

from .. import APP_DISPLAY_NAME, __version__
from ..backend.tools import source_tool, which
from ..config import Settings
from ..detection import detect_kind, detect_source, source_label
from ..gui.dialogs import HistoryDialog, LogsDialog, DoctorDialog, SettingsDialog
from ..gui.widgets import OptionsStack, ActionButtons, SOURCE_LABELS
from ..history import is_completely_done, last_destination
from ..jobs import JobController
from ..logging_ import info
from ..notify import notify
from ..paths import default_download_dir
from ..queue import QueueItem, QueueModel
from ..utils import human_bytes, is_valid_url, redact

STATUS_COLORS = {
    "waiting": "#b8a8ff",
    "downloading": "#00e5ff",
    "paused": "#ffb300",
    "completed": "#00d97a",
    "failed": "#ff5c66",
    "cancelled": "#8a92a8",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_DISPLAY_NAME} {__version__}")
        self.resize(1100, 720)

        self.settings = Settings()
        self.model = QueueModel()
        self.controller = JobController(self.model, self.settings)
        self.rows: dict[str, dict] = {}

        self._build_ui()
        self._connect_controller()
        self.model.on_change(self._sync_rows)
        self._sync_rows()

        self.statusBar().showMessage(
            f"Ready. Downloads go to {self.settings.get('download_dir')}"
        )

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        # ----- header
        header = QHBoxLayout()
        icon = QLabel("▶▼")
        icon.setFixedSize(36, 36)
        icon.setStyleSheet(
            "color: #00e5ff; font-size: 28px; background: #161922; "
            "border: 1px solid #3a4055; border-radius: 8px;"
        )
        title = QLabel(f"<b>{APP_DISPLAY_NAME}</b>")
        title.setStyleSheet("font-size: 20px; color: #00e5ff; letter-spacing: 1px;")
        subtitle = QLabel(
            f"<small>v{__version__}</small>  ·  YouTube · Google Drive · MEGA · Direct URLs"
        )
        subtitle.setStyleSheet("color: #8890a8;")
        header.addWidget(icon)
        header.addWidget(title)
        header.addSpacing(8)
        header.addWidget(subtitle)
        header.addStretch()
        state_light = QLabel("IDLE")
        state_light.setObjectName("StatusLabel")
        self.state_light = state_light
        header.addWidget(state_light)
        root.addLayout(header)

        # ----- link bar
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        bar = QHBoxLayout()
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText(
            "Paste a download link (YouTube, Google Drive, MEGA or direct URL)"
        )
        self.url_entry.returnPressed.connect(self.on_add)
        self.btn_paste = QPushButton("Paste")
        self.btn_paste.setFixedWidth(66)
        self.btn_paste.clicked.connect(self.on_paste)
        self.source_combo = QComboBox()
        self.source_combo.addItem("Auto-detect", "auto")
        for source in ["youtube", "gdrive", "mega", "direct"]:
            self.source_combo.addItem(SOURCE_LABELS[source], source)
        self.source_combo.setFixedWidth(150)
        self.btn_detect = QPushButton("Detect")
        self.btn_detect.setFixedWidth(70)
        self.btn_detect.clicked.connect(self.on_detect)
        self.btn_add = QPushButton("Add to queue")
        self.btn_add.setObjectName("Primary")
        self.btn_add.clicked.connect(self.on_add)
        self.detected_label = QLabel("")
        self.detected_label.setStyleSheet("color: #8890a8; font-size: 12px;")
        bar.addWidget(QLabel("Link:"), 0)
        bar.addWidget(self.url_entry, 1)
        bar.addWidget(self.btn_paste)
        bar.addWidget(QLabel("Source:"), 0)
        bar.addWidget(self.source_combo)
        bar.addWidget(self.btn_detect)
        bar.addWidget(self.btn_add)
        card_layout.addLayout(bar)
        card_layout.addWidget(self.detected_label)
        root.addWidget(card)

        # ----- options
        self.options_box = QGroupBox("Download options")
        opts_layout = QVBoxLayout(self.options_box)
        self.options_stack = OptionsStack()
        self.options_stack.setFixedHeight(170)
        opts_layout.addWidget(self.options_stack)
        root.addWidget(self.options_box)

        # ----- queue
        self.queue_table = QTableWidget(0, 6)
        self.queue_table.setHorizontalHeaderLabels(
            ["Name", "Source", "Status", "Progress", "Size · Speed · ETA", "Actions"]
        )
        self.queue_table.verticalHeader().hide()
        self.queue_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue_table.setAlternatingRowColors(True)
        header_view = self.queue_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4, 5):
            header_view.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.queue_table, 1)

        # ----- bottom bar
        bottom = QHBoxLayout()
        self.btn_folder = QPushButton("Open download folder")
        self.btn_folder.clicked.connect(self.open_folder)
        self.btn_history = QPushButton("History")
        self.btn_history.clicked.connect(self.show_history)
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.clicked.connect(self.show_settings)
        self.btn_logs = QPushButton("Logs")
        self.btn_logs.clicked.connect(self.show_logs)
        self.btn_doctor = QPushButton("Dependency doctor")
        self.btn_doctor.clicked.connect(self.show_doctor)
        self.btn_clear = QPushButton("Clear completed")
        self.btn_clear.clicked.connect(self.clear_completed)
        for btn in (self.btn_folder, self.btn_history, self.btn_settings, self.btn_logs,
                    self.btn_doctor, self.btn_clear):
            btn.setObjectName("Ghost")
            bottom.addWidget(btn)
        bottom.addStretch()
        self.status_label = QLabel("No downloads yet")
        bottom.addWidget(self.status_label)
        root.addLayout(bottom)

    # ------------------------------------------------------------------ controller wiring

    def _connect_controller(self) -> None:
        self.controller.jobProgress.connect(self.on_job_progress)
        self.controller.jobState.connect(self.on_job_state)
        self.controller.jobFinished.connect(self.on_job_finished)
        self.controller.jobLog.connect(self.on_job_log)

    # ------------------------------------------------------------------ link bar actions

    def on_paste(self) -> None:
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self.url_entry.setText(text)
            self.on_detect()

    def on_detect(self) -> None:
        url = self.url_entry.text().strip()
        if not url:
            self.detected_label.setText("Paste a link first.")
            return
        if not is_valid_url(url):
            self.detected_label.setText("That does not look like a valid http(s) link.")
            self.detected_label.setStyleSheet("color: #ff5c66;")
            return
        source = detect_source(url)
        kind = detect_kind(source, url)
        self.source_combo.setCurrentText(SOURCE_LABELS.get(source, "Unknown"))
        self.options_stack.show_source(source)
        self.options_stack.set_kind(source, kind)
        tool = source_tool(source)
        hint = ""
        if tool and not which(tool):
            hint = f"  ({tool} not installed)"
        self.detected_label.setText(
            f"Detected: {SOURCE_LABELS.get(source, 'Unknown')} ({kind}){hint}"
        )
        self.detected_label.setStyleSheet("color: #00d97a; font-size: 12px;")
        info("detection", f"{url} -> {source} ({kind})")

    def on_add(self) -> None:
        url = self.url_entry.text().strip()
        if not url:
            return
        if not is_valid_url(url):
            QMessageBox.warning(self, "Invalid link", "Please paste a valid http(s) link.")
            return

        source_index = self.source_combo.currentData()
        if source_index == "auto":
            source = detect_source(url)
        else:
            source = source_index
        kind = detect_kind(source, url)
        self.options_stack.show_source(source)
        self.options_stack.set_kind(source, kind)

        dest = str(self.settings.get("download_dir"))

        # Never re-download what is already finished.
        if is_completely_done(url):
            prev = last_destination(url) or dest
            item = QueueItem(
                id="", url=url, source=source, kind=kind,
                title=source_label(source) + " " + kind,
                destination=prev, state="completed",
                progress=100.0, skip_reason="Already downloaded",
            )
            self.model.add(item)
            self.url_entry.clear()
            self.detected_label.setText("")
            notify("Universal Downloader", f"Already downloaded: {item.title}")
            return

        item = QueueItem(
            id="", url=url, source=source, kind=kind,
            title=source_label(source) + " " + kind,
            destination=dest, state="waiting",
            options=self.options_stack.options(),
        )
        self.controller.add(item)
        self.url_entry.clear()
        self.detected_label.setText("")
        info("queue", f"added {source}/{kind}: {redact(url)}")

    def open_folder(self) -> None:
        folder = str(self.settings.get("download_dir"))
        Path(folder).mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def show_history(self) -> None:
        dlg = HistoryDialog(self)
        dlg.exec()

    def show_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self.controller, self)
        dlg.exec()
        self.statusBar().showMessage(
            f"Downloads go to {self.settings.get('download_dir')}"
        )

    def show_logs(self) -> None:
        dlg = LogsDialog(self)
        dlg.exec()

    def show_doctor(self) -> None:
        dlg = DoctorDialog(self)
        dlg.exec()

    def clear_completed(self) -> None:
        self.model.clear_completed()

    # ------------------------------------------------------------------ queue sync

    def _sync_rows(self) -> None:
        known = {item.id for item in self.model.list_items()}
        for item_id in list(self.rows):
            if item_id not in known:
                self._remove_row(item_id)
        for item in self.model.list_items():
            if item.id not in self.rows:
                self._add_row(item)
            else:
                self._refresh_row(item)

    def _add_row(self, item: QueueItem) -> None:
        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(item.progress or 0))
        widgets = {
            "name": QTableWidgetItem(item.title or item.url),
            "source": QTableWidgetItem(
                f"{SOURCE_LABELS.get(item.source, item.source)} · {item.kind}"
            ),
            "status": QTableWidgetItem(item.state.title()),
            "progress": bar,
            "info": QTableWidgetItem(""),
            "actions": ActionButtons(item.id),
        }
        self.queue_table.setItem(row, 0, widgets["name"])
        self.queue_table.setItem(row, 1, widgets["source"])
        self.queue_table.setItem(row, 2, widgets["status"])
        self.queue_table.setCellWidget(row, 3, bar)
        self.queue_table.setItem(row, 4, widgets["info"])
        self.queue_table.setCellWidget(row, 5, widgets["actions"])
        self.rows[item.id] = {"row": row, "widgets": widgets}
        widgets["actions"].requested.connect(self.on_row_action)
        self._apply_state_colors(widgets, item.state)
        self._refresh_row(item)

    def _remove_row(self, item_id: str) -> None:
        entry = self.rows.pop(item_id, None)
        if entry:
            self.queue_table.removeRow(entry["row"])
            self._rebuild_row_indices()

    def _rebuild_row_indices(self) -> None:
        for index, (item_id, entry) in enumerate(self.rows.items()):
            entry["row"] = index

    def _refresh_row(self, item: QueueItem) -> None:
        entry = self.rows.get(item.id)
        if not entry:
            return
        widgets = entry["widgets"]
        widgets["status"].setText(item.state.title())
        widgets["source"].setText(
            f"{SOURCE_LABELS.get(item.source, item.source)} · {item.kind}"
        )
        row = entry["row"]
        bar = self.queue_table.cellWidget(row, 3)
        if isinstance(bar, QProgressBar):
            bar.setValue(int(item.progress or 0))
        if item.downloaded or item.total:
            text = f"{human_bytes(item.downloaded)} / {human_bytes(item.total)}"
        else:
            text = "- / -"
        if item.speed:
            text += f"  ·  {human_bytes(item.speed)}/s"
        if item.eta:
            text += f"  ·  ETA {item.eta}"
        if item.status_message:
            text += f"  [{item.status_message}]"
        widgets["info"].setText(text)
        widgets["actions"].set_state(item.state)
        self._apply_state_colors(widgets, item.state)

    def _apply_state_colors(self, widgets: dict, state: str) -> None:
        color = QColor(STATUS_COLORS.get(state, "#e8e8f0"))
        widgets["status"].setForeground(QBrush(color))

    def on_job_progress(self, item_id: str, update: dict) -> None:
        item = self.model.get(item_id)
        if item:
            self._refresh_row(item)

    def on_job_state(self, item_id: str, state: str) -> None:
        item = self.model.get(item_id)
        if item:
            self._refresh_row(item)

    def on_job_finished(self, item_id: str, result: dict) -> None:
        item = self.model.get(item_id)
        if not item:
            return
        if result.get("state") == "completed":
            notify("Universal Downloader", f"Finished: {item.title}")
        elif result.get("state") == "failed":
            notify(
                "Universal Downloader",
                f"Failed: {item.title} — {result.get('error', '')}",
            )
        self._refresh_row(self.model.get(item_id))
        completed = sum(1 for i in self.model.list_items() if i.state == "completed")
        failed = sum(1 for i in self.model.list_items() if i.state == "failed")
        self.status_label.setText(f"{completed} completed, {failed} failed")

    def on_job_log(self, item_id: str, line: str) -> None:
        item = self.model.get(item_id)
        if item:
            self.model.update_progress(item_id, status_message=line[:90])

    def on_row_action(self, item_id: str, action: str) -> None:
        if action == "pause":
            self.controller.pause_job(item_id)
        elif action == "resume":
            self.controller.resume_job(item_id)
        elif action == "cancel":
            self.controller.cancel_job(item_id)
        elif action == "retry":
            self.controller.retry_job(item_id)
        elif action == "remove":
            self.controller.remove_job(item_id)
        elif action == "open":
            item = self.model.get(item_id)
            if item:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(item.destination))))
