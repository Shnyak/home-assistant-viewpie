from custom_components.viewpie.api_client import _is_valid_jpeg_snapshot


def test_jpeg_snapshot_accepts_binary_start_and_end_markers():
    assert _is_valid_jpeg_snapshot(bytes((0xFF, 0xD8, 0xFF, 0xD9)))


def test_jpeg_snapshot_rejects_missing_or_textual_markers():
    assert not _is_valid_jpeg_snapshot(b"\\xff\\xd8payload\\xff\\xd9")
    assert not _is_valid_jpeg_snapshot(bytes((0x00, 0xD8, 0xFF, 0xD9)))
    assert not _is_valid_jpeg_snapshot(bytes((0xFF, 0xD8, 0xFF, 0x00)))
    assert not _is_valid_jpeg_snapshot(b"")
