"""Universal Downloader 2.0.5 - lightweight gaming-styled download manager.

A PyQt6 desktop GUI for YouTube (yt-dlp), Google Drive (gdown), MEGA
(MEGAcmd) and direct file links (aria2c).

The download backends are adapter-wrapped subprocesses: no file is ever loaded
entirely into RAM, downloads run as background jobs, and the GUI stays
responsive on low-end hardware (4 GB RAM, dual-core CPU).
"""

__version__ = "2.0.5"
APP_NAME = "universal-downloader"
APP_DISPLAY_NAME = "Universal Downloader"
ORGANIZATION = "Universal Downloader"

# XDG-conformant locations. Personal data never lives inside /opt.
CONFIG_DIR_NAME = APP_NAME
DATA_DIR_NAME = APP_NAME
CACHE_DIR_NAME = APP_NAME

# Default download location (can be overridden in settings).
DEFAULT_DOWNLOAD_DIR = "~/Videos"
