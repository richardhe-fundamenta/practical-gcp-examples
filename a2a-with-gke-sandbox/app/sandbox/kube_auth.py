"""Make the k8s-agent-sandbox SDK able to reach the GKE control plane from Cloud Run.

The SDK's K8sHelper loads its client via `config.load_kube_config()` — i.e. it reads a
kubeconfig *file* and ignores any in-memory `Configuration.set_default()`. So we write a
kubeconfig pointing at the cluster's DNS-based control-plane endpoint, authenticated with the
ambient Google service-account token, and point `$KUBECONFIG` at it.

The DNS endpoint presents publicly-trusted TLS, so no CA is needed (system trust store). The
`GKE_CA_CERT` env (base64 PEM) is honored for the private-endpoint case: it is embedded as
`certificate-authority-data`.

ponytail: refresh-per-call, no token cache. Tokens last ~1h and we rewrite the kubeconfig per
request (fresh SandboxClient per request); add caching if refresh latency ever matters.
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile

import google.auth
import google.auth.transport.requests

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
KUBECONFIG_PATH = pathlib.Path(tempfile.gettempdir()) / "a2a-gke-kubeconfig.json"


def install_default_k8s_config(*, endpoint: str, ca_cert_path: str | None = None) -> None:
    """Write a kubeconfig for the GKE DNS endpoint + ambient SA token and export KUBECONFIG.

    Args:
        endpoint: the cluster's DNS control-plane endpoint (bare FQDN, no scheme).
        ca_cert_path: unused with the DNS endpoint (kept for signature compatibility); the CA,
            when needed, is embedded inline from the GKE_CA_CERT env var.
    """
    creds, _ = google.auth.default(scopes=_SCOPES)
    creds.refresh(google.auth.transport.requests.Request())

    cluster: dict = {"server": f"https://{endpoint}"}
    gke_ca_cert = os.environ.get("GKE_CA_CERT")  # base64-encoded PEM, for private endpoints
    if gke_ca_cert:
        cluster["certificate-authority-data"] = gke_ca_cert

    kubeconfig = {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{"name": "gke", "cluster": cluster}],
        "users": [{"name": "gke", "user": {"token": creds.token}}],
        "contexts": [{"name": "gke", "context": {"cluster": "gke", "user": "gke"}}],
        "current-context": "gke",
    }
    # JSON is valid YAML, so load_kube_config() parses it fine — avoids a yaml dependency.
    # Write owner-only (0600): the file holds a short-lived SA bearer token. It lives only in
    # the trusted Cloud Run container's ephemeral fs (the untrusted sandbox never sees it), but
    # restrict reads as defense-in-depth.
    KUBECONFIG_PATH.write_text(json.dumps(kubeconfig))
    os.chmod(KUBECONFIG_PATH, 0o600)
    os.environ["KUBECONFIG"] = str(KUBECONFIG_PATH)
