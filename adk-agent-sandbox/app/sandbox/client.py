"""Thin client that executes model-generated render code inside the Vertex AI
Agent Runtime Code Execution sandbox, passing a data.json input file and
returning a named output artifact (a PNG or other binary).

Discovered SDK shape (vertexai 1.149.0):
  - Client: vertexai.Client(location="us-central1")
  - Method: client.agent_engines.sandboxes.execute_code(
        name=<sandbox_resource_name>,
        input_data={
            "code": <python_code_str>,
            "files": [{"name": <filename>, "mimeType": <mime>, "content": <bytes>}],
        },
    )
  - Returns: ExecuteSandboxEnvironmentResponse(outputs=list[Chunk])
  - Each Chunk has:
      .data       -> bytes  (the chunk payload)
      .mime_type  -> str    (e.g. "image/png", "text/plain")
      .metadata   -> Metadata with .attributes: dict[str, bytes]
                     where attributes["file_name"] == b"<filename>"
  - There is NO explicit stdout/stderr field; print() output arrives as a
    Chunk with mime_type="text/plain" and no metadata.attributes["file_name"].
  - Output files are identified by metadata.attributes["file_name"].
"""

from __future__ import annotations

import vertexai

# Session-state key under which the current session's sandbox resource name is cached.
# Plain (unprefixed) key => session-scoped: each session gets its own sandbox, isolating
# users from one another and letting an expired sandbox be transparently recreated.
SANDBOX_NAME_KEY = "sandbox_name"

# Display name for sandboxes the harness creates on demand under the host Agent Engine.
_SANDBOX_DISPLAY_NAME = "analyst-harness-sandbox"


class SandboxError(Exception):
    """Raised when sandbox execution fails or the expected artifact is missing."""


def _client_default(location: str = "us-central1") -> vertexai.Client:  # type: ignore[name-defined]
    return vertexai.Client(location=location)


def _create_sandbox(engine_name: str, client) -> str:
    """Create a Python code-exec sandbox under ``engine_name`` and return its resource name.

    Imports the spec types lazily so the module import stays light and does not depend
    on the ``vertexai._genai`` internals at load time.
    """
    from vertexai._genai.types.common import (
        Language,
        SandboxEnvironmentSpec,
        SandboxEnvironmentSpecCodeExecutionEnvironment,
    )

    spec = SandboxEnvironmentSpec(
        code_execution_environment=SandboxEnvironmentSpecCodeExecutionEnvironment(
            code_language=Language.LANGUAGE_PYTHON,
            machine_config=None,  # default: ~2000 milliGCU, 1.5 GiB RAM
        )
    )
    operation = client.agent_engines.sandboxes.create(
        name=engine_name,
        spec=spec,
        config={"display_name": _SANDBOX_DISPLAY_NAME, "wait_for_completion": True},
    )
    sandbox = getattr(operation, "response", None)
    name = getattr(sandbox, "name", None) if sandbox is not None else None
    if not name:
        raise SandboxError(
            f"Sandbox creation under {engine_name!r} returned no resource name."
        )
    return name


def _refresh_sandbox(engine_name: str, tool_context, client) -> str:
    """Create a fresh sandbox and cache its name in session state, replacing any prior one."""
    name = _create_sandbox(engine_name, client)
    tool_context.state[SANDBOX_NAME_KEY] = name
    return name


def get_or_create_sandbox(engine_name: str, tool_context, *, _client=None) -> str:
    """Return this session's sandbox resource name, creating one under ``engine_name``
    (a durable host Agent Engine) on first use and caching it in ``tool_context.state``.

    Args:
        engine_name:   Resource name of the persistent host Agent Engine (reasoningEngine).
        tool_context:  ADK ToolContext; its ``.state`` holds the per-session sandbox name.
        _client:       Optional pre-built client (used by tests to inject a mock).
    """
    name = tool_context.state.get(SANDBOX_NAME_KEY)
    if name:
        return name
    client = _client or _client_default()
    return _refresh_sandbox(engine_name, tool_context, client)


def _is_stale_sandbox_error(exc: Exception) -> bool:
    """True if ``exc`` indicates the cached sandbox (or its host engine) no longer exists.

    Agent Engine code-exec sandboxes have a TTL; once expired, execute returns
    ``404 NOT_FOUND`` or ``400 FAILED_PRECONDITION``. We treat those — and a missing-code
    fallback on the message — as a signal to recreate. Other failures are not retried.
    """
    code = getattr(exc, "code", None)
    status = str(getattr(exc, "status", "") or "")
    blob = f"{status} {exc}".upper()
    if code == 404:
        return True
    if code == 400 and "FAILED_PRECONDITION" in blob:
        return True
    if code is None and ("NOT_FOUND" in blob or "FAILED_PRECONDITION" in blob):
        return True
    return False


def execute_in_sandbox(
    *,
    code: str,
    data_json: str,
    out_name: str,
    engine_name: str,
    tool_context,
    _client=None,
) -> bytes:
    """Run render code in this session's sandbox, lazily creating one under ``engine_name``
    and self-healing if the cached sandbox has expired.

    Looks up (or creates) the session's sandbox, executes once, and on a stale-sandbox
    error recreates a fresh sandbox and retries exactly once. Non-stale failures (e.g. a
    missing output artifact) propagate without retry.

    Args:
        code:          Python source to execute in the sandbox.
        data_json:     JSON string exposed as ``data.json`` inside the sandbox.
        out_name:      Expected output filename (e.g. ``"output.png"``).
        engine_name:   Resource name of the persistent host Agent Engine.
        tool_context:  ADK ToolContext; ``.state`` caches the per-session sandbox name.
        _client:       Optional pre-built client (used by tests to inject a mock).

    Returns:
        Raw bytes of the named output artifact.

    Raises:
        SandboxError:  If the sandbox emits error output or the expected artifact is absent.
    """
    client = _client or _client_default()
    name = get_or_create_sandbox(engine_name, tool_context, _client=client)
    try:
        return run_in_sandbox(
            code=code, data_json=data_json, out_name=out_name,
            resource_name=name, _client=client,
        )
    except Exception as exc:
        if not _is_stale_sandbox_error(exc):
            raise

    # Stale sandbox: drop it, create a fresh one under the host engine, retry exactly once.
    name = _refresh_sandbox(engine_name, tool_context, client)
    return run_in_sandbox(
        code=code, data_json=data_json, out_name=out_name,
        resource_name=name, _client=client,
    )


def _extract_file_name(chunk) -> str | None:
    """Return the file_name stored in a Chunk's metadata attributes, or None."""
    try:
        attrs = chunk.metadata.attributes
        raw = attrs.get("file_name", b"")
        return raw.decode("utf-8") if raw else None
    except AttributeError:
        return None


def run_in_sandbox(
    *,
    code: str,
    data_json: str,
    out_name: str,
    resource_name: str,
    _client=None,
) -> bytes:
    """Execute model-generated render code in the isolated sandbox with data.json
    as an input file; return the named output artifact bytes.

    Args:
        code:            Python source code to execute in the sandbox.
        data_json:       JSON string to expose as ``data.json`` inside the sandbox.
        out_name:        Expected output filename (e.g. ``"output.png"``).
        resource_name:   Fully-qualified sandbox resource name, e.g.
                         ``"projects/p/locations/us-central1/reasoningEngines/r/sandboxEnvironments/s"``.
        _client:         Optional pre-built client (used by tests to inject a mock).

    Returns:
        Raw bytes of the named output artifact.

    Raises:
        SandboxError:    If the sandbox emits error output or the expected artifact
                         is not present in the response.
    """
    client = _client or _client_default()

    resp = client.agent_engines.sandboxes.execute_code(
        name=resource_name,
        input_data={
            "code": code,
            "files": [
                {
                    "name": "data.json",
                    "mimeType": "application/json",
                    "content": data_json.encode("utf-8"),
                }
            ],
        },
    )

    # Collect outputs.  The SDK returns Chunk objects with:
    #   mime_type="text/plain"  -> stdout/print output (no file_name in metadata)
    #   mime_type=<image/...>   -> output file (file_name in metadata.attributes)
    outputs = getattr(resp, "outputs", None) or []

    stdout_chunks: list[str] = []
    file_map: dict[str, bytes] = {}

    for chunk in outputs:
        fname = _extract_file_name(chunk)
        if fname:
            file_map[fname] = chunk.data or b""
        else:
            # Likely a text/plain chunk containing print output or error text.
            if chunk.data:
                try:
                    stdout_chunks.append(chunk.data.decode("utf-8", errors="replace"))
                except Exception:
                    pass

    stdout_text = "".join(stdout_chunks)

    # Heuristic error detection: if there's text output but no output file,
    # treat the text as an error message.
    if out_name not in file_map:
        detail = stdout_text[:2000] if stdout_text else "(no text output)"
        raise SandboxError(
            f"Expected artifact {out_name!r} not produced by sandbox. "
            f"Captured output: {detail}"
        )

    return file_map[out_name]
