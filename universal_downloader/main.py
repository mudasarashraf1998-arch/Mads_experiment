"""Application entry point: universal-downloader (GUI)."""

from __future__ import annotations

import sys

from .gui.app import UniversalDownloaderApp
from .gui.window import MainWindow


def main() -> int:
    app = UniversalDownloaderApp(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
