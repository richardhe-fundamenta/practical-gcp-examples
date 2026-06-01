import importlib
from app import config


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj")
    monkeypatch.setenv("BQ_DATA_REGION", "EU")
    monkeypatch.setenv("BQ_MAX_BYTES_BILLED", "1073741824")
    monkeypatch.setenv("BQ_DATASET_ALLOWLIST", "analytics,public_data")
    monkeypatch.setenv("SANDBOX_RESOURCE_NAME", "projects/p/locations/us-central1/sandboxes/s")
    importlib.reload(config)
    s = config.get_settings()
    assert s.project == "proj"
    assert s.bq_data_region == "EU"
    assert s.max_bytes_billed == 1073741824
    assert s.dataset_allowlist == {"analytics", "public_data"}
    assert s.sandbox_region == "us-central1"
