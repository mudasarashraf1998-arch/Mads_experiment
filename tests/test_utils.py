from universal_downloader.utils import (
    safe_name, human_bytes, parse_bytes, format_speed, format_eta,
    redact, redact_url, is_valid_url, url_host, unique_path,
)


def test_safe_name():
    assert safe_name("Season 4 / Episode: 01") == "Season 4 - Episode - 01"
    assert safe_name("  weird<>:./name  ") == "weird - - - . - name"
    assert safe_name("") == "untitled"
    assert safe_name("A" * 300) == ("A" * 150)


def test_redact():
    assert "<hidden>" in redact("https://user:pass@mega.nz/file/abc#veryLongSecretKeyHere")
    assert "secret" not in redact("https://mega.nz/file/abc#veryLongSecretKeyHere")
    assert "<hidden>" in redact("https://example.com/file?token=abc123secret")
    assert "<hidden>" in redact("Cookie: session=secretsessionvalue")


def test_human_bytes():
    assert human_bytes(0) == "0 B"
    assert human_bytes(1024) == "1.0 KB"
    assert human_bytes(1024**3) == "1.0 GB"


def test_parse_bytes():
    assert parse_bytes("1.5GB") == int(1.5 * 1000**3)
    assert parse_bytes("1024") == 1024
    assert parse_bytes("5M") == 5_000_000


def test_url_validation():
    assert is_valid_url("https://example.com/file.bin")
    assert not is_valid_url("not a url")
    assert not is_valid_url("https://example.com/has space")
    assert url_host("https://drive.google.com/file/d/1?x=1") == "drive.google.com"


def test_unique_path(tmp_path):
    base = tmp_path / "file.txt"
    base.write_text("x")
    assert unique_path(base) == tmp_path / "file (1).txt"
    (tmp_path / "file (1).txt").write_text("y")
    assert unique_path(base) == tmp_path / "file (2).txt"
