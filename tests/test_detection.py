from universal_downloader.detection import detect_source, detect_kind, source_label


CASES = [
    ("https://drive.google.com/drive/folders/1AbCd", "gdrive", "Folder"),
    ("https://drive.google.com/file/d/1vqX5KDUs25YL18lRz9cpFnRxsW1ZKIsi/view", "gdrive", "File"),
    ("https://docs.google.com/document/d/abc/edit", "gdrive", "File"),
    ("https://mega.nz/file/abc123#secretKey", "mega", "File"),
    ("https://mega.nz/folder/abc123#key", "mega", "Folder"),
    ("https://mega.nz/#F!abc!key", "mega", "Folder"),
    ("https://youtu.be/dQw4w", "youtube", "Video"),
    ("https://www.youtube.com/watch?v=dQw4w", "youtube", "Video"),
    ("https://www.youtube.com/playlist?list=PLabc", "youtube", "Playlist"),
    ("https://music.youtube.com/playlist?list=PLabc", "youtube", "Playlist"),
    ("https://example.com/file.iso", "direct", "File"),
    ("https://my-own.site/downloads/x.zip", "direct", "File"),
]


def test_source_detection():
    for url, source, kind in CASES:
        assert detect_source(url) == source, url
        assert detect_kind(source, url) == kind, url


def test_source_labels():
    assert source_label("gdrive") == "Google Drive"
    assert source_label("mega") == "MEGA"
    assert source_label("youtube") == "YouTube"
    assert source_label("direct") == "Direct file link"
