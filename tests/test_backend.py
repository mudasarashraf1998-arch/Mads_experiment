"""Unit tests for backend adapters without running any subprocess downloads."""

from pathlib import Path
from unittest.mock import patch

import pytest

from universal_downloader.backend.adapter import DownloadOptions
from universal_downloader.backend.youtube import YouTubeAdapter, _parse_size
from universal_downloader.backend.direct import probe, DirectAdapter
from universal_downloader.backend.gdrive import extract_id
from universal_downloader.backend.mega import parse_link


def test_youtube_format_args_with_ffmpeg():
    opts = DownloadOptions(source="youtube", destination="/tmp/d", title="t",
                           extra={"yt_mode": "video", "yt_quality": "1080",
                                  "yt_container": "mp4", "yt_audio": "best",
                                  "yt_playlist": "full", "yt_numbering": True,
                                  "yt_archive": True})
    adapter = YouTubeAdapter(opts)
    args = adapter._yt_format_args(have_ffmpeg=True)
    assert "--merge-output-format" in args
    assert "mp4" in args
    assert any("height<=1080" in a for a in args)


def test_youtube_format_args_without_ffmpeg():
    opts = DownloadOptions(source="youtube", destination="/tmp/d", title="t",
                           extra={"yt_mode": "video", "yt_quality": "best",
                                  "yt_container": "mkv", "yt_audio": "best",
                                  "yt_playlist": "single", "yt_numbering": False,
                                  "yt_archive": False})
    adapter = YouTubeAdapter(opts)
    args = adapter._yt_format_args(have_ffmpeg=False)
    assert args == ["--format", "b"]


def test_youtube_audio_best_keeps_original():
    opts = DownloadOptions(source="youtube", destination="/tmp/d", title="t",
                           extra={"yt_mode": "audio", "yt_quality": "best",
                                  "yt_container": "mkv", "yt_audio": "best",
                                  "yt_playlist": "single", "yt_numbering": True,
                                  "yt_archive": True})
    adapter = YouTubeAdapter(opts)
    args = adapter._yt_format_args(have_ffmpeg=True)
    assert "--extract-audio" not in args
    assert args == ["--format", "ba/b"]


def test_parse_size():
    assert _parse_size("45.23MiB") == int(45.23 * 1024**2)
    assert _parse_size("1.5GB") == int(1.5 * 1000**3)
    assert _parse_size("100") == 0  # no unit -> 0 by our strict parser


def test_gdrive_extract_id():
    assert extract_id("https://drive.google.com/file/d/1vqX5KDUs25YL18lRz9cpFnRxsW1ZKIsi/view") == "1vqX5KDUs25YL18lRz9cpFnRxsW1ZKIsi"
    assert extract_id("https://drive.google.com/drive/folders/1gT5U85") == "1gT5U85"
    assert extract_id("https://example.com/notdrive") is None


def test_mega_parse_link():
    assert parse_link("https://mega.nz/file/abc123#key") == ("file", "abc123")
    assert parse_link("https://mega.nz/#F!folderId!key") == ("folder", "folderId")
    assert parse_link("https://example.com/") is None


FAKE_CURL_HEADERS = """HTTP/1.1 200 OK
content-length: 1048576
content-disposition: attachment; filename="Movie (2024).mkv"

"""


def test_direct_probe(monkeypatch):
    class FakeResult:
        stdout = FAKE_CURL_HEADERS
    with patch("subprocess.run", return_value=FakeResult()):
        info = probe("https://example.com/file.mkv")
    assert info["size"] == 1048576
    assert info["name"] == "Movie (2024).mkv"


def test_direct_adapter_options():
    opts = DownloadOptions(source="direct", destination="/tmp/d", title="t",
                           extra={"direct_connections": 8, "retries": 3, "retry_wait": 5})
    adapter = DirectAdapter(opts)
    assert adapter.options.extra["direct_connections"] == 8


def test_aria2_control_parsing():
    xml = "<aria2 version=\"1.36.0\"><file><index>1</index><length>5242880</length><totalLength>10485760</totalLength></file></aria2>"
    import re
    match = re.search(r"<length>(\d+)</length>.*?<totalLength>(\d+)</totalLength>", xml, re.S)
    assert match and int(match.group(1)) == 5242880 and int(match.group(2)) == 10485760
