"""Qt application bootstrap with the gaming dark theme."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QLocale
from PyQt6.QtGui import QIcon, QPalette, QColor
from PyQt6.QtWidgets import QApplication

from .. import __version__, APP_DISPLAY_NAME, ORGANIZATION
from ..paths import cache_dir


class UniversalDownloaderApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("universal-downloader")
        self.setApplicationDisplayName(APP_DISPLAY_NAME)
        self.setApplicationVersion(__version__)
        self.setOrganizationName(ORGANIZATION)
        self.setDesktopFileName("universal-downloader.desktop")

        # Single instance is not enforced; a second launch simply opens a new
        # window showing the same queue (stored in XDG data dir).
        self._apply_palette()
        self._apply_stylesheet()
        QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedKingdom))

    def _apply_palette(self) -> None:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#0b0c10"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8e8f0"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#11131a"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#161922"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#e8e8f0"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#161922"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e8e8f0"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#00e5ff"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
        self.setPalette(palette)
        self.setStyle("Fusion")

    def _apply_stylesheet(self) -> None:
        qss = Path(__file__).with_name("theme.qss")
        if qss.exists():
            self.setStyleSheet(qss.read_text(encoding="utf-8"))

    def icon_name(self) -> str:
        return "universal-downloader"
