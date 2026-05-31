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


class SandboxError(Exception):
    """Raised when sandbox execution fails or the expected artifact is missing."""


def _client_default(location: str = "us-central1") -> vertexai.Client:  # type: ignore[name-defined]
    return vertexai.Client(location=location)


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
