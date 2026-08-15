import json
import os


class GCS:
    """Thin wrapper over google-cloud-storage for a single bucket."""

    def __init__(self, bucket_name, client=None):
        if client is None:
            from google.cloud import storage
            client = storage.Client()
        self.client = client
        self.bucket_name = bucket_name
        self.bucket = client.bucket(bucket_name)

    def upload_file(self, local_path, blob_name):
        self.bucket.blob(blob_name).upload_from_filename(local_path)

    def download_file(self, blob_name, local_path):
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        self.bucket.blob(blob_name).download_to_filename(local_path)

    def upload_json(self, obj, blob_name):
        self.bucket.blob(blob_name).upload_from_string(
            json.dumps(obj, indent=2), content_type="application/json"
        )

    def download_json(self, blob_name):
        return json.loads(self.bucket.blob(blob_name).download_as_text())

    def download_bytes(self, blob_name):
        return self.bucket.blob(blob_name).download_as_bytes()

    def upload_dir(self, local_dir, prefix):
        for root, _, files in os.walk(local_dir):
            for fn in files:
                lp = os.path.join(root, fn)
                rel = os.path.relpath(lp, local_dir).replace(os.sep, "/")
                self.upload_file(lp, f"{prefix}/{rel}")

    def list_blobs(self, prefix):
        return [b.name for b in self.client.list_blobs(self.bucket, prefix=prefix)]

    def list_blobs_meta(self, prefix):
        """[(name, time_created)] — for sorting by actual upload time, which
        name-sort can't do across mixed naming schemes."""
        return [(b.name, b.time_created)
                for b in self.client.list_blobs(self.bucket, prefix=prefix)]
