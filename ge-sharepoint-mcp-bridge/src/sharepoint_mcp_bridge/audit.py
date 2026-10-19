# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He
"""Request token extraction and one-JSON-line-per-call audit logging."""

import contextvars
import functools
import hashlib
import json
import os
import time
import uuid

import httpx
import jwt
from fastmcp.server.dependencies import get_http_headers

GOOGLE_ISSUER = "https://accounts.google.com"
_target: contextvars.ContextVar[dict] = contextvars.ContextVar("audit_target")


class BridgeError(ValueError):
    """Input/policy error with an explicit error code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _claims(token: str) -> dict:
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return {}


def request_token(required: bool = True) -> str:
    """Entra access token from Authorization (Graph validates it), else MS_GRAPH_ACCESS_TOKEN."""
    # FastMCP strips authorization unless asked for explicitly.
    auth = get_http_headers(include={"authorization"}).get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if token and _claims(token).get("iss") == GOOGLE_ISSUER:
        token = ""  # Cloud Run invoker ID token, not a Graph token
    token = token or os.environ.get("MS_GRAPH_ACCESS_TOKEN", "").strip()
    if not token and required:
        raise PermissionError("No Microsoft Entra access token on the request. Reconnect your account.")
    return token


def mask_upn(upn: str) -> str:
    if "@" not in upn:
        return "unknown"
    local, domain = upn.split("@", 1)
    return f"{local[:2]}***@{domain}"


def user_info(token: str) -> dict:
    """Unverified Entra claims for correlation only. Never includes the token."""
    c = _claims(token) if token else {}
    upn = str(c.get("upn") or c.get("preferred_username") or c.get("unique_name") or c.get("email") or "")
    oid, tid = str(c.get("oid", "unknown")), str(c.get("tid", "unknown"))
    return {
        "entra_oid": oid,
        "tenant_id": tid,
        "upn_masked": mask_upn(upn),
        "user_hash": hashlib.sha256(f"{tid}:{oid}:{upn}".encode()).hexdigest()[:16] if c else None,
        "scopes": c.get("scp", ""),
        "app_id": c.get("appid") or c.get("azp"),
    }


def note(**fields) -> None:
    """Add target details (drive_id, item_id, ...) to the current call's audit line."""
    t = _target.get(None)
    if t is not None:
        t.update({k: v for k, v in fields.items() if v is not None})


def _error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, BridgeError):
        return exc.code, str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        hint = {401: "token rejected or expired", 403: "access denied", 404: "not found",
                409: "an item with that name already exists", 423: "file is locked",
                429: "throttled, retry shortly"}.get(code, "request failed")
        return f"GRAPH_HTTP_{code}", f"Microsoft Graph returned HTTP {code}: {hint}."
    if isinstance(exc, PermissionError):
        return "AUTH_TOKEN_MISSING", str(exc)
    if isinstance(exc, FileNotFoundError):
        return "NOT_FOUND", str(exc)
    if isinstance(exc, (ValueError, KeyError, IndexError)):
        return "INVALID_INPUT", str(exc)
    return "INTERNAL_ERROR", "Unexpected server error."


def emit(tool: str, category: str, outcome: str, latency_ms: float, target: dict,
         error_code: str | None = None) -> str:
    audit_id = str(uuid.uuid4())
    headers = get_http_headers()
    rec = {
        "severity": "INFO" if outcome == "SUCCESS" else "ERROR",
        "event_type": "MCP_BRIDGE_AUDIT",
        "audit_id": audit_id,
        "tool": tool,
        "category": category,
        "outcome": outcome,
        "error_code": error_code,
        "latency_ms": round(latency_ms, 1),
        "user": user_info(request_token(required=False)),
        "target": target,
    }
    project, trace = os.environ.get("GOOGLE_CLOUD_PROJECT"), headers.get("x-cloud-trace-context", "")
    if project and trace:
        rec["logging.googleapis.com/trace"] = f"projects/{project}/traces/{trace.split('/')[0]}"
    print(json.dumps(rec, default=str), flush=True)
    return audit_id


def audited(category: str):
    """Wrap an async tool: emit one audit line, turn exceptions into safe error dicts."""

    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            target = {k: kwargs[k] for k in ("drive", "file_name", "item_id", "folder_path", "list_name",
                                             "site", "action", "link_type", "scope") if kwargs.get(k)}
            token = _target.set(target)
            start = time.monotonic()
            try:
                result = await fn(*args, **kwargs)
                ms = (time.monotonic() - start) * 1000
                return {"status": "success", **result, "audit_id": emit(fn.__name__, category, "SUCCESS", ms, target)}
            except Exception as exc:  # noqa: BLE001 - every failure becomes an audited error
                code, msg = _error(exc)
                ms = (time.monotonic() - start) * 1000
                return {"status": "error", "error_code": code, "message": msg,
                        "audit_id": emit(fn.__name__, category, "ERROR", ms, target, code)}
            finally:
                _target.reset(token)

        return wrapper

    return deco
