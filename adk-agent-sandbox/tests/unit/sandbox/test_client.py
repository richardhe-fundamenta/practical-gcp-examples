"""Unit tests for app.sandbox.client.

The Vertex AI Sandboxes API (vertexai 1.149.0) shape:
  sandboxes.execute_code(name=..., input_data={"code": ..., "files": [...]})
  -> ExecuteSandboxEnvironmentResponse(outputs=list[Chunk])

Each Chunk:
  .data        -> bytes
  .mime_type   -> str  (e.g. "image/png", "text/plain")
  .metadata    -> object with .attributes: dict[str, bytes]
                  where attributes["file_name"] == b"<filename>"

Output files are identified by metadata.attributes["file_name"].
Text/plain chunks with no file_name in metadata carry print()/stdout text.
There is NO separate stdout/stderr field on the response.
"""

from unittest.mock import MagicMock

import pytest

from app.sandbox.client import SandboxError, run_in_sandbox

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _make_file_chunk(filename: str, data: bytes, mime_type: str = "image/png"):
    """Create a realistic Chunk mock for an output file."""
    chunk = MagicMock()
    chunk.data = data
    chunk.mime_type = mime_type
    chunk.metadata = MagicMock()
    chunk.metadata.attributes = {"file_name": filename.encode("utf-8")}
    return chunk


def _make_text_chunk(text: str):
    """Create a realistic Chunk mock for stdout/print output (no file_name)."""
    chunk = MagicMock()
    chunk.data = text.encode("utf-8")
    chunk.mime_type = "text/plain"
    chunk.metadata = MagicMock()
    # No "file_name" key — this is raw print output, not a named file.
    chunk.metadata.attributes = {}
    return chunk


def _make_fake_client(outputs):
    """Build a minimal fake vertexai client whose sandboxes.execute_code returns
    an ExecuteSandboxEnvironmentResponse-like object with the given outputs."""
    resp = MagicMock()
    resp.outputs = outputs

    fake = MagicMock()
    fake.agent_engines.sandboxes.execute_code.return_value = resp
    return fake


# ---------------------------------------------------------------------------
# Test 1 – happy path: output file present in response
# ---------------------------------------------------------------------------


def test_returns_named_output_file():
    """run_in_sandbox returns the bytes of the expected output file."""
    outputs = [
        _make_text_chunk("wrote output.png"),
        _make_file_chunk("output.png", PNG_BYTES, "image/png"),
    ]
    fake = _make_fake_client(outputs)

    result = run_in_sandbox(
        code="print('wrote output.png')",
        data_json="{}",
        out_name="output.png",
        resource_name="projects/p/locations/us-central1/reasoningEngines/r/sandboxEnvironments/s",
        _client=fake,
    )

    assert result == PNG_BYTES
    fake.agent_engines.sandboxes.execute_code.assert_called_once_with(
        name="projects/p/locations/us-central1/reasoningEngines/r/sandboxEnvironments/s",
        input_data={
            "code": "print('wrote output.png')",
            "files": [
                {
                    "name": "data.json",
                    "mimeType": "application/json",
                    "content": b"{}",
                }
            ],
        },
    )


# ---------------------------------------------------------------------------
# Test 2 – failure: expected artifact not produced
# ---------------------------------------------------------------------------


def test_missing_output_raises_sandbox_error():
    """run_in_sandbox raises SandboxError when the expected file is absent."""
    outputs = [
        _make_text_chunk("Traceback (most recent call last):\n  ...\nValueError: boom"),
    ]
    fake = _make_fake_client(outputs)

    with pytest.raises(SandboxError, match="output.png"):
        run_in_sandbox(
            code="raise ValueError('boom')",
            data_json="{}",
            out_name="output.png",
            resource_name="r",
            _client=fake,
        )


# ---------------------------------------------------------------------------
# Test 3 – failure: empty outputs (no chunks at all)
# ---------------------------------------------------------------------------


def test_empty_outputs_raises_sandbox_error():
    """run_in_sandbox raises SandboxError when no chunks are returned."""
    fake = _make_fake_client(outputs=[])

    with pytest.raises(SandboxError):
        run_in_sandbox(
            code="# nothing",
            data_json="{}",
            out_name="output.png",
            resource_name="r",
            _client=fake,
        )


# ---------------------------------------------------------------------------
# Test 4 – multiple output files: the correct one is returned
# ---------------------------------------------------------------------------


def test_returns_correct_file_among_multiple():
    """run_in_sandbox returns only the requested file when multiple are present."""
    other_bytes = b"other data"
    outputs = [
        _make_file_chunk("other.csv", other_bytes, "text/csv"),
        _make_file_chunk("output.png", PNG_BYTES, "image/png"),
    ]
    fake = _make_fake_client(outputs)

    result = run_in_sandbox(
        code="...",
        data_json="{}",
        out_name="output.png",
        resource_name="r",
        _client=fake,
    )

    assert result == PNG_BYTES
