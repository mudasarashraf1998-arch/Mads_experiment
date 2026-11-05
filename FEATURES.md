# Universal Downloader 2.0.3 — feature status

✅ = fully implemented and tested  |  ⚠️ = implemented with limitations  |  ❌ = not yet implemented

## Interface
- [✅] GTK-free native GUI (PyQt6 Qt6 widgets), dark gaming theme, cyan/magenta accents
- [✅] Application menu entry (.desktop) and icon
- [✅] Link paste link bar with Paste button, URL validation
- [✅] Automatic source detection (YouTube / Drive / MEGA / direct)
- [✅] Manual source-selection dropdown overriding detection
- [✅] Detect button
- [✅] Add to queue
- [✅] Source-specific options panels
- [✅] Queue table: name, source, status, progress bar, size/speed/ETA
- [✅] Pause/resume (where the backend supports it), cancel, retry, remove completed, open folder
- [✅] Bottom bar: open download folder, history, settings, logs, dependency doctor
- [✅] Usable on 1366x768

## YouTube
- [✅] Video / audio download type
- [✅] Quality list: best, 2160p, 1440p, 1080p, 720p, 480p, 360p
- [✅] Container: MP4 / MKV with ffmpeg merge
- [✅] Audio: best/original stream (no conversion), MP3 320/192/128
- [✅] Single video / full playlist
- [✅] Playlist title as destination folder, numbering
- [✅] Download archive skip, resume partial downloads
- [✅] Retry transient errors
- [⚠️] Meaningful errors for private/deleted/blocked videos (classified as fatal)
- [❌] "Only offer resolutions actually available for the selected video" — fixed quality list; a live format probe is not yet wired

## Google Drive
- [✅] Public files and folders
- [✅] Folder title from Drive page (fallback: Google-Drive-<id>)
- [✅] Resume (gdown --continue), skip complete, retry
- [⚠️] Quota/permission errors stop retries immediately and are explained
- [❌] per-file gdown failure inspection scoped to current attempt (basic version implemented)

## MEGA
- [✅] File and folder links, staging + rename to real names
- [⚠️] Interrupted-download recovery via re-run into same staging folder
- [✅] Skip complete, retry, MEGA keys redacted in logs
- [❌] Avoid duplicate MEGA daemon instances (not applicable: mega-get is stateless per invocation)

## Direct URL
- [✅] aria2c, segmented connections, Content-Disposition names
- [✅] Resume from .aria2 control file, skip when server size matches
- [❌] Never assumes a size-unknown local file is complete
- [✅] No unexpected overwrites (allow-overwrite=false)

## Queue
- [✅] Persistent queue (JSON), states: waiting/downloading/paused/completed/failed/cancelled
- [✅] Real progress from subprocess output (no simulation)
- [✅] Throttled updates, no high-frequency polling
- [✅] Default 1 concurrent download, configurable max 2
- [✅] Auto-retry on transient errors

## History / settings / logs
- [✅] History: name, source, link (redacted), destination, date/time, status
- [✅] Settings: directory, concurrency, retries, YouTube defaults, notifications
- [✅] XDG paths under ~/.config, ~/.local/share, ~/.cache
- [✅] Per-run logs, log viewer dialog

## Packaging
- [✅] universal-downloader_2.0.3_all.deb, /opt install, menu entry, icon
- [✅] Dependencies registered; missing tools explained in-app
- [✅] Uninstall preserves user data
- [✅] SHA-256 checksums

## Testing
- [✅] Automated tests: detection, URLs, options construction, queue, history, resume/skip logic
- [⚠️] GUI tests skipped on headless build systems (no Qt platform plugin)
- [❌] Real-download tests (excluded by design — no real downloads in automated tests)
