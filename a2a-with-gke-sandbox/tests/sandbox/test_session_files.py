from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.sandbox import session_files as sf


def _fake_storage():
    """A storage.Client() whose bucket().blob()/list_blobs() are inspectable."""
    bucket = MagicMock()
    client = MagicMock()
    client.bucket.return_value = bucket
    return client, bucket


@patch.object(sf, "_BUCKET", "test-bucket")
def test_persist_uploads_writes_under_session_prefix():
    client, bucket = _fake_storage()
    with patch.object(sf.storage, "Client", return_value=client):
        sf.persist_uploads("conv-1", [("data.csv", b"a,b\n1,2\n")])
    bucket.blob.assert_called_once_with("session-uploads/conv-1/data.csv")
    bucket.blob.return_value.upload_from_string.assert_called_once_with(b"a,b\n1,2\n")


@patch.object(sf, "_BUCKET", "test-bucket")
def test_persist_uploads_empty_is_noop():
    client, bucket = _fake_storage()
    with patch.object(sf.storage, "Client", return_value=client):
        sf.persist_uploads("conv-1", [])
    bucket.blob.assert_not_called()


@patch.object(sf, "_BUCKET", "test-bucket")
def test_load_session_files_downloads_all_and_strips_prefix():
    client, bucket = _fake_storage()
    blobs = [
        SimpleNamespace(name="session-uploads/conv-1/", download_as_bytes=lambda: b""),  # placeholder
        SimpleNamespace(name="session-uploads/conv-1/data.csv", download_as_bytes=lambda: b"PNG"),
    ]
    bucket.list_blobs.return_value = blobs
    with patch.object(sf.storage, "Client", return_value=client):
        out = sf.load_session_files("conv-1")
    assert out == [("data.csv", b"PNG")]
    bucket.list_blobs.assert_called_once_with(prefix="session-uploads/conv-1/")


@patch.object(sf, "_BUCKET", "test-bucket")
def test_session_file_names_lists_names_only():
    client, bucket = _fake_storage()
    bucket.list_blobs.return_value = [
        SimpleNamespace(name="session-uploads/conv-1/"),
        SimpleNamespace(name="session-uploads/conv-1/a.csv"),
        SimpleNamespace(name="session-uploads/conv-1/b.xlsx"),
    ]
    with patch.object(sf.storage, "Client", return_value=client):
        assert sf.session_file_names("conv-1") == ["a.csv", "b.xlsx"]
