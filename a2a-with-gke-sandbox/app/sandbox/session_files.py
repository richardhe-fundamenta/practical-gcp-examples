"""Persist a turn's uploaded files to GCS per conversation, then re-hydrate them next turn.

The sandbox is fresh per request and Gemini Enterprise only attaches a file on the turn the user
uploads it — so a follow-up like "now make it a pie chart" arrives with no file. We stash each
turn's uploads in GCS keyed by the **conversation id** (== A2A contextId == ADK session id, the
isolation boundary) and load the whole set back on every turn, so the file is always there.

Bucket: `UPLOADS_BUCKET`, else the logs bucket (`LOGS_BUCKET_NAME`). We avoid `CHART_BUCKET` on
purpose — that one has a 1-day lifecycle for ephemeral chart images, too short for a conversation.
"""
from __future__ import annotations

import os

from google.cloud import storage

_BUCKET = os.environ.get("UPLOADS_BUCKET") or os.environ.get("LOGS_BUCKET_NAME")
_PREFIX = "session-uploads"
# Cap how much we re-hydrate into a sandbox (defensive; per-file cap is enforced on upload).
_MAX_TOTAL_BYTES = 20 * 1024 * 1024


def _bucket():
    if not _BUCKET:
        raise RuntimeError("no uploads bucket configured (set UPLOADS_BUCKET or LOGS_BUCKET_NAME)")
    return storage.Client().bucket(_BUCKET)


def _session_prefix(session_id: str) -> str:
    return f"{_PREFIX}/{session_id}/"


def persist_uploads(session_id: str, files: list[tuple[str, bytes]]) -> None:
    """Upload this turn's files under the conversation's prefix (no-op for an empty list)."""
    if not files:
        return
    bucket = _bucket()
    for name, data in files:
        bucket.blob(f"{_session_prefix(session_id)}{name}").upload_from_string(data)


def load_session_files(session_id: str) -> list[tuple[str, bytes]]:
    """Return every file stored for the conversation as (name, bytes), up to the size cap."""
    out: list[tuple[str, bytes]] = []
    total = 0
    for blob in _bucket().list_blobs(prefix=_session_prefix(session_id)):
        name = blob.name.rsplit("/", 1)[-1]
        if not name:  # the prefix "directory" placeholder
            continue
        data = blob.download_as_bytes()
        total += len(data)
        if total > _MAX_TOTAL_BYTES:
            break
        out.append((name, bytes(data)))
    return out


def session_file_names(session_id: str) -> list[str]:
    """Just the filenames stored for the conversation (cheap; no downloads)."""
    names = []
    for blob in _bucket().list_blobs(prefix=_session_prefix(session_id)):
        name = blob.name.rsplit("/", 1)[-1]
        if name:
            names.append(name)
    return names
