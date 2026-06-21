import base64
import json
import os
from unittest.mock import patch, MagicMock

import pytest

from app.sandbox import kube_auth


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    # Redirect the kubeconfig output to a temp file and keep KUBECONFIG clean per test.
    monkeypatch.setattr(kube_auth, "KUBECONFIG_PATH", tmp_path / "kubeconfig.json")
    monkeypatch.delenv("KUBECONFIG", raising=False)
    yield


def _run(endpoint="10.0.0.2", token="tok-123", **kwargs):
    fake_creds = MagicMock(token=token)
    with patch("app.sandbox.kube_auth.google.auth.default",
               return_value=(fake_creds, "proj")), \
         patch("app.sandbox.kube_auth.google.auth.transport.requests.Request"):
        kube_auth.install_default_k8s_config(endpoint=endpoint, **kwargs)
    return fake_creds


def test_writes_kubeconfig_and_exports_env(monkeypatch):
    """DNS endpoint (no GKE_CA_CERT): kubeconfig has server+token, no CA, KUBECONFIG set."""
    monkeypatch.delenv("GKE_CA_CERT", raising=False)
    fake = _run(endpoint="gke.example.com", token="tok-abc")

    path = kube_auth.KUBECONFIG_PATH
    assert os.environ["KUBECONFIG"] == str(path)
    kc = json.loads(path.read_text())
    cluster = kc["clusters"][0]["cluster"]
    assert cluster["server"] == "https://gke.example.com"
    assert "certificate-authority-data" not in cluster   # system trust for DNS endpoint
    assert kc["users"][0]["user"]["token"] == "tok-abc"
    assert kc["current-context"] == "gke"
    fake.refresh.assert_called_once()


def test_ca_cert_embedded_when_env_set(monkeypatch):
    """GKE_CA_CERT set: embedded inline as certificate-authority-data (private endpoint case)."""
    b64 = base64.b64encode(b"PEMDATA").decode()
    monkeypatch.setenv("GKE_CA_CERT", b64)
    _run()
    kc = json.loads(kube_auth.KUBECONFIG_PATH.read_text())
    assert kc["clusters"][0]["cluster"]["certificate-authority-data"] == b64


def test_ca_cert_path_optional(monkeypatch):
    """ca_cert_path may be omitted (the DNS-endpoint default) without error."""
    monkeypatch.delenv("GKE_CA_CERT", raising=False)
    _run(endpoint="gke.example.com")  # no ca_cert_path
    assert kube_auth.KUBECONFIG_PATH.exists()
