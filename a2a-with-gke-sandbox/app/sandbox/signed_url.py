"""Upload a generated file to GCS and return a short-lived V4 signed URL.

Used to host chart images so the agent can reference them from an A2UI Image component
(which requires a fetchable URL, not inline bytes). Signing uses the IAM signBlob API via the
ambient service-account token — no key file — so the runtime SA needs
`roles/iam.serviceAccountTokenCreator` on itself.
"""
from __future__ import annotations

import datetime
import os
import uuid

import google.auth
from google.auth.transport import requests as google_requests
from google.cloud import storage

# Bucket for hosted outputs (reuse the ADK artifact/logs bucket by default).
_BUCKET = os.environ.get("CHART_BUCKET") or os.environ.get("LOGS_BUCKET_NAME")
# Short TTL by default to limit exposure — long enough for the client to fetch the image when
# the agent replies. Signed URLs are NOT single-use: valid for any number of GETs until this
# window elapses. Tune via SIGNED_URL_TTL_MINUTES. Trade-off: if the chat UI re-fetches the
# URL when a conversation is revisited after this window, the chart will no longer load.
_TTL_MINUTES = int(os.environ.get("SIGNED_URL_TTL_MINUTES", "15"))


def upload_and_sign(data: bytes, filename: str, content_type: str) -> str:
    """Upload bytes to GCS under a unique prefix and return a V4 signed GET URL.

    Raises RuntimeError if no bucket is configured.
    """
    if not _BUCKET:
        raise RuntimeError("no output bucket configured (set CHART_BUCKET or LOGS_BUCKET_NAME)")

    creds, _ = google.auth.default()
    creds.refresh(google_requests.Request())

    blob = storage.Client(credentials=creds).bucket(_BUCKET).blob(
        f"a2ui-outputs/{uuid.uuid4().hex}/{filename}"
    )
    blob.upload_from_string(data, content_type=content_type)

    # Sign via IAM signBlob (no private key): pass the SA email + access token.
    return blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=_TTL_MINUTES),
        method="GET",
        service_account_email=os.environ.get("SIGNING_SERVICE_ACCOUNT")
        or getattr(creds, "service_account_email", None),
        access_token=creds.token,
    )
