# Universal Downloader 2.0.2

Lightweight gaming-styled graphical download manager for Linux Mint 22.3 /
Ubuntu 24.04 (amd64). Paste a link, pick your options, download — no terminal
required.

Supported sources: **YouTube (yt-dlp)**, **Google Drive (gdown)**, **MEGA
(MEGAcmd)** and **direct file links (aria2c)**.

## Screenshots in words

Dark theme with neon cyan/magenta accents, a link bar with paste/detect/add,
source-specific download options (YouTube type/quality/container/audio,
playlist handling), a persistent queue with real progress bars, speed and ETA,
and a bottom bar with download folder, history, settings, logs and a
dependency doctor.

## Install

```bash
sudo apt install ./universal-downloader_2.0.3_all.deb
```

Then open **Universal Downloader** from the application menu (XFCE: Menu →
Multimedia/Internet, or search "Universal Downloader"). No terminal needed.

The .deb installs the application under `/opt/universal-downloader/`, creates
`/usr/bin/universal-downloader`, a desktop-menu entry and an icon. It does not
touch `~/Scripts/universal-downloader` (your existing 2.0.1 terminal install,
if any) and uninstalling never deletes downloads, history, configuration or
logs.

## Runtime dependencies (detected automatically)

| Source | Tool | Install hint |
|--------|------|--------------|
| YouTube | yt-dlp | `sudo apt install yt-dlp` |
| Google Drive | gdown | `python3 -m pip install --user --upgrade gdown` |
| MEGA | mega-get (MEGAcmd) | https://mega.io/cmd → `sudo apt install ./megacmd-*.deb` |
| Direct links | aria2c | `sudo apt install aria2` |
| YouTube merge/audio | ffmpeg | `sudo apt install ffmpeg` (recommended) |
| Notifications | notify-send | `sudo apt install libnotify-bin` |

The in-app **Dependency doctor** shows exactly what is installed and what is
missing, with copy-and-paste install commands. The GUI launches and works for
whatever sources have their tools installed.

## Where personal data lives

- Settings: `~/.config/universal-downloader/settings.conf`
- History & queue: `~/.local/share/universal-downloader/`
- Logs: `~/.cache/universal-downloader/logs/`
- Downloads: `~/Videos` by default (configurable in Settings)

Uninstall (`sudo apt remove universal-downloader`) removes only the
application files; your downloads, history, settings and logs are preserved.

## Architecture

The GUI talks to download tools through backend adapters
(`universal_downloader/backend/`): one adapter per source, each wrapping the
CLI tool as a subprocess, reading real progress line-by-line (no polling, no
files loaded into RAM) and reporting state through a persistent queue model
with one active download by default (configurable up to two).

The existing terminal backend (v2.0.1, `~/Scripts/universal-downloader/`) is
**not modified**. The GUI re-implements the same semantics (resume, archive,
skip-complete, `.ud-complete` markers, redaction) in Python adapters so the
package is self-contained; the adapter architecture maps one-to-one onto the
shell modules so a later integration can delegate to them without rewriting the
GUI.

## Building the .deb

```bash
./scripts/build-deb.sh
```

Requires `dpkg-deb`. Produces `universal-downloader_2.0.3_all.deb` plus a
SHA-256 checksum file.

## Testing

```bash
./tests/run_tests.sh
```

Tests use mocked downloader processes — no real downloads, no network. GUI
tests are skipped on headless systems without the Qt platform libraries.

## Feature completeness

See `FEATURES.md` for the implemented vs. not-yet-implemented list.

## Security

- Downloaded files are never opened or executed automatically.
- URLs are validated; sensitive parameters (MEGA keys, tokens, user:pass) are
  redacted in logs and history.
- VirusTotal-style uploading is deliberately not included.
