"""Reusable widgets: source-specific options and queue row actions."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QPushButton, QRadioButton, QScrollArea,
    QSizePolicy, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

SOURCE_ORDER = ["youtube", "gdrive", "mega", "direct"]
SOURCE_LABELS = {
    "youtube": "YouTube",
    "gdrive": "Google Drive",
    "mega": "MEGA",
    "direct": "Direct URL",
}

YT_QUALITIES = [
    ("best", "Best available"),
    ("2160", "2160p / 4K"),
    ("1440", "1440p"),
    ("1080", "1080p"),
    ("720", "720p"),
    ("480", "480p"),
    ("360", "360p"),
]
YT_AUDIO = [
    ("best", "Best available / original audio"),
    ("mp3-320", "MP3 320 kbps"),
    ("mp3-192", "MP3 192 kbps"),
    ("mp3-128", "MP3 128 kbps"),
]


class OptionsPanel(QWidget):
    """Base class for a source's option panel; returns a dict of options."""

    def options(self) -> dict:
        return {}


class YouTubeOptions(OptionsPanel):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Download type
        type_box = QGroupBox("Download type")
        type_layout = QHBoxLayout(type_box)
        self.mode_video = QRadioButton("Video")
        self.mode_audio = QRadioButton("Audio")
        self.mode_video.setChecked(True)
        group = QButtonGroup(type_box)
        group.addButton(self.mode_video, 0)
        group.addButton(self.mode_audio, 1)
        type_layout.addWidget(self.mode_video)
        type_layout.addWidget(self.mode_audio)
        type_layout.addStretch()
        layout.addWidget(type_box)

        grid = QGridLayout()
        row = 0

        self.quality = QComboBox()
        for value, label in YT_QUALITIES:
            self.quality.addItem(label, value)
        self.quality.setCurrentText("Best available")
        grid.addWidget(QLabel("Video quality"), row, 0)
        grid.addWidget(self.quality, row, 1)
        row += 1

        self.container = QComboBox()
        self.container.addItems(["MKV", "MP4"])
        grid.addWidget(QLabel("Video container"), row, 0)
        grid.addWidget(self.container, row, 1)
        row += 1

        self.audio = QComboBox()
        for value, label in YT_AUDIO:
            self.audio.addItem(label, value)
        grid.addWidget(QLabel("Audio quality"), row, 0)
        grid.addWidget(self.audio, row, 1)
        row += 1

        layout.addLayout(grid)

        # Playlist behaviour
        pl_box = QGroupBox("Playlist behaviour")
        pl_layout = QVBoxLayout(pl_box)
        self.playlist_full = QRadioButton("Whole playlist")
        self.playlist_single = QRadioButton("Single video")
        self.playlist_full.setChecked(True)
        pgroup = QButtonGroup(pl_box)
        pgroup.addButton(self.playlist_full, 0)
        pgroup.addButton(self.playlist_single, 1)
        pl_layout.addWidget(self.playlist_full)
        pl_layout.addWidget(self.playlist_single)

        opts = QHBoxLayout()
        self.numbering = QCheckBox("Number playlist files")
        self.numbering.setChecked(True)
        self.archive = QCheckBox("Skip already archived videos")
        self.archive.setChecked(True)
        opts.addWidget(self.numbering)
        opts.addWidget(self.archive)
        opts.addStretch()
        pl_layout.addLayout(opts)
        layout.addWidget(pl_box)

        # Enable/disable audio-specific rows depending on mode
        self.mode_audio.toggled.connect(self._refresh_visibility)
        self.mode_video.toggled.connect(self._refresh_visibility)
        self._refresh_visibility()

    def _refresh_visibility(self) -> None:
        audio = self.mode_audio.isChecked()
        self.quality.setEnabled(not audio)
        self.container.setEnabled(not audio)
        self.audio.setEnabled(audio)

    def options(self) -> dict:
        return {
            "yt_mode": "audio" if self.mode_audio.isChecked() else "video",
            "yt_quality": self.quality.currentData(),
            "yt_container": self.container.currentText().lower(),
            "yt_audio": self.audio.currentData(),
            "yt_playlist": "full" if self.playlist_full.isChecked() else "single",
            "yt_numbering": self.numbering.isChecked(),
            "yt_archive": self.archive.isChecked(),
        }


class GDriveOptions(OptionsPanel):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        note = QLabel(
            "Public Google Drive files and folders are supported. "
            "The real folder/file title is used as the destination folder."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8890a8; font-size: 12px;")
        layout.addWidget(note)
        self.kind_label = QLabel("Kind: detected when added")
        layout.addWidget(self.kind_label)
        layout.addStretch()

    def set_kind(self, kind: str) -> None:
        self.kind_label.setText(f"Kind: {kind}")

    def options(self) -> dict:
        return {}


class MegaOptions(OptionsPanel):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        note = QLabel(
            "MEGA file and folder links via MEGAcmd (mega-get). "
            "Transfers resume into the same staging folder on retry."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8890a8; font-size: 12px;")
        layout.addWidget(note)
        self.kind_label = QLabel("Kind: detected when added")
        layout.addWidget(self.kind_label)
        layout.addStretch()

    def set_kind(self, kind: str) -> None:
        self.kind_label.setText(f"Kind: {kind}")

    def options(self) -> dict:
        return {}


class DirectOptions(OptionsPanel):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        grid = QGridLayout()
        self.connections = QSpinBox()
        self.connections.setRange(1, 8)
        self.connections.setValue(4)
        grid.addWidget(QLabel("Connections per server"), 0, 0)
        grid.addWidget(self.connections, 0, 1)
        note = QLabel(
            "aria2c with resume and segmented downloads. "
            "Existing files are never overwritten."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8890a8; font-size: 12px;")
        layout.addLayout(grid)
        layout.addWidget(note)
        layout.addStretch()

    def options(self) -> dict:
        return {"direct_connections": self.connections.value()}


class OptionsStack(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.panels: dict[str, OptionsPanel] = {
            "youtube": YouTubeOptions(),
            "gdrive": GDriveOptions(),
            "mega": MegaOptions(),
            "direct": DirectOptions(),
        }
        for panel in self.panels.values():
            self.addWidget(panel)

    def show_source(self, source: str) -> None:
        panel = self.panels.get(source)
        if panel:
            self.setCurrentWidget(panel)

    def options(self) -> dict:
        panel = self.currentWidget()
        return panel.options() if panel else {}

    def set_kind(self, source: str, kind: str) -> None:
        panel = self.panels.get(source)
        if hasattr(panel, "set_kind"):
            panel.set_kind(kind)


class ActionButtons(QWidget):
    """Per-row action buttons, enabled according to the item state."""

    requested = pyqtSignal(str, str)  # item_id, action

    def __init__(self, item_id: str):
        super().__init__()
        self.item_id = item_id
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        self.pause = QPushButton("Pause")
        self.pause.setObjectName("Ghost")
        self.pause.setFixedWidth(62)
        self.resume = QPushButton("Resume")
        self.resume.setObjectName("Ghost")
        self.resume.setFixedWidth(66)
        self.cancel = QPushButton("Cancel")
        self.cancel.setObjectName("Danger")
        self.cancel.setFixedWidth(62)
        self.retry = QPushButton("Retry")
        self.retry.setObjectName("Ghost")
        self.retry.setFixedWidth(58)
        self.remove = QPushButton("Remove")
        self.remove.setObjectName("Danger")
        self.remove.setFixedWidth(66)
        self.open_folder = QPushButton("Open")
        self.open_folder.setObjectName("Ghost")
        self.open_folder.setFixedWidth(56)

        for btn, action in (
            (self.pause, "pause"), (self.resume, "resume"),
            (self.cancel, "cancel"), (self.retry, "retry"),
            (self.remove, "remove"), (self.open_folder, "open"),
        ):
            btn.clicked.connect(lambda _, a=action: self.requested.emit(self.item_id, a))
            layout.addWidget(btn)

        layout.addStretch()
        self.set_state("waiting")

    def set_state(self, state: str) -> None:
        self.pause.setVisible(False)
        self.resume.setVisible(False)
        self.cancel.setVisible(False)
        self.retry.setVisible(False)
        self.remove.setVisible(False)
        self.open_folder.setVisible(False)

        if state in ("waiting", "downloading"):
            self.pause.setVisible(True)
            self.cancel.setVisible(True)
            self.pause.setEnabled(state == "downloading")
        elif state == "paused":
            self.resume.setVisible(True)
            self.cancel.setVisible(True)
        elif state == "failed":
            self.retry.setVisible(True)
            self.remove.setVisible(True)
        elif state == "cancelled":
            self.remove.setVisible(True)
        elif state == "completed":
            self.open_folder.setVisible(True)
            self.remove.setVisible(True)
