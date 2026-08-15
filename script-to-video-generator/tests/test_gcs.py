import os
from deck.infra.gcs import GCS


class FakeBlob:
    def __init__(self, store, times, seq, name):
        self.store = store
        self.times = times
        self.seq = seq  # shared 1-element list: a monotonic upload counter
        self.name = name

    @property
    def time_created(self):
        return self.times.get(self.name, 0)

    def _stamp(self):
        self.seq[0] += 1
        self.times[self.name] = self.seq[0]

    def upload_from_filename(self, path):
        with open(path, "rb") as f:
            self.store[self.name] = f.read()
        self._stamp()

    def upload_from_string(self, data, content_type=None):
        self.store[self.name] = data.encode() if isinstance(data, str) else data
        self._stamp()

    def download_to_filename(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as f:
            f.write(self.store[self.name])

    def download_as_text(self):
        return self.store[self.name].decode()

    def download_as_bytes(self):
        return self.store[self.name]


class FakeBucket:
    def __init__(self, store, times, seq):
        self.store = store
        self.times = times
        self.seq = seq

    def blob(self, name):
        return FakeBlob(self.store, self.times, self.seq, name)


class FakeClient:
    def __init__(self):
        self.store = {}
        self.times = {}
        self.seq = [0]

    def bucket(self, name):
        return FakeBucket(self.store, self.times, self.seq)

    def list_blobs(self, bucket, prefix=""):
        return [FakeBlob(self.store, self.times, self.seq, n)
                for n in self.store if n.startswith(prefix)]


def test_upload_and_download_json():
    gcs = GCS("b", client=FakeClient())
    gcs.upload_json({"a": 1}, "jobs/x.json")
    assert gcs.download_json("jobs/x.json") == {"a": 1}


def test_upload_dir_and_list(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "f1.txt").write_text("one")
    (tmp_path / "sub" / "f2.txt").write_text("two")
    gcs = GCS("b", client=FakeClient())
    gcs.upload_dir(str(tmp_path), "runs/1")
    names = set(gcs.list_blobs("runs/1"))
    assert "runs/1/f1.txt" in names
    assert "runs/1/sub/f2.txt" in names
