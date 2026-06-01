"""Unit tests for the per-session sandbox lifecycle (lazy get-or-create + stale retry).

The harness no longer pins a single shared SANDBOX_RESOURCE_NAME. Instead each
session lazily creates a sandbox under a durable host Agent Engine, caches its name
in ``tool_context.state``, reuses it within the session, and self-heals when the
sandbox expires (Agent Engine code-exec sandboxes have a TTL): a ``404 NOT_FOUND``
or ``400 FAILED_PRECONDITION`` on execute triggers exactly one recreate-and-retry.
"""

from unittest.mock import MagicMock

import pytest

from app.sandbox.client import (
    SANDBOX_NAME_KEY,
    SandboxError,
    execute_in_sandbox,
    get_or_create_sandbox,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
ENGINE = "projects/p/locations/us-central1/reasoningEngines/r"


class FakeAPIError(Exception):
    """Mimics the genai SDK error surface (.code / .status)."""

    def __init__(self, code=None, status="", message=""):
        super().__init__(message or status or f"error {code}")
        self.code = code
        self.status = status


class Ctx:
    """Minimal stand-in for ToolContext — only ``.state`` is used here."""

    def __init__(self, state=None):
        self.state = dict(state or {})


def _file_chunk(name: str, data: bytes):
    c = MagicMock()
    c.data = data
    c.mime_type = "image/png"
    c.metadata.attributes = {"file_name": name.encode("utf-8")}
    return c


def _ok_response(name: str = "output.png", data: bytes = PNG):
    resp = MagicMock()
    resp.outputs = [_file_chunk(name, data)]
    return resp


def _fake_client(*, create_names=("sb-1",), execute_side_effect=None, execute_return=None):
    """Fake vertexai client whose sandboxes.create returns the given names in order
    and whose execute_code yields the given response(s)."""
    fake = MagicMock()
    ops = []
    for n in create_names:
        op = MagicMock()
        op.response.name = n
        ops.append(op)
    fake.agent_engines.sandboxes.create.side_effect = ops
    if execute_side_effect is not None:
        fake.agent_engines.sandboxes.execute_code.side_effect = execute_side_effect
    else:
        fake.agent_engines.sandboxes.execute_code.return_value = execute_return or _ok_response()
    return fake


# ---------------------------------------------------------------------------
# get_or_create_sandbox
# ---------------------------------------------------------------------------


def test_get_or_create_returns_cached_without_creating():
    ctx = Ctx({SANDBOX_NAME_KEY: "sb-cached"})
    fake = _fake_client()

    name = get_or_create_sandbox(ENGINE, ctx, _client=fake)

    assert name == "sb-cached"
    fake.agent_engines.sandboxes.create.assert_not_called()


def test_get_or_create_creates_and_stores_when_absent():
    ctx = Ctx()
    fake = _fake_client(create_names=("sb-new",))

    name = get_or_create_sandbox(ENGINE, ctx, _client=fake)

    assert name == "sb-new"
    assert ctx.state[SANDBOX_NAME_KEY] == "sb-new"
    fake.agent_engines.sandboxes.create.assert_called_once()
    # created under the supplied host engine
    assert fake.agent_engines.sandboxes.create.call_args.kwargs["name"] == ENGINE


# ---------------------------------------------------------------------------
# execute_in_sandbox — happy path
# ---------------------------------------------------------------------------


def test_execute_uses_cached_sandbox_and_returns_bytes():
    ctx = Ctx({SANDBOX_NAME_KEY: "sb-1"})
    fake = _fake_client(execute_return=_ok_response())

    out = execute_in_sandbox(
        code="c", data_json="{}", out_name="output.png",
        engine_name=ENGINE, tool_context=ctx, _client=fake,
    )

    assert out == PNG
    fake.agent_engines.sandboxes.create.assert_not_called()
    assert fake.agent_engines.sandboxes.execute_code.call_args.kwargs["name"] == "sb-1"


# ---------------------------------------------------------------------------
# execute_in_sandbox — stale sandbox self-heals (recreate + retry once)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "err",
    [
        FakeAPIError(code=404, status="NOT_FOUND"),
        FakeAPIError(code=400, status="FAILED_PRECONDITION"),
        FakeAPIError(message="404 NOT_FOUND: sandbox gone"),  # no structured code
    ],
)
def test_execute_recreates_on_stale_error_and_retries(err):
    ctx = Ctx({SANDBOX_NAME_KEY: "sb-stale"})
    fake = _fake_client(create_names=("sb-fresh",), execute_side_effect=[err, _ok_response()])

    out = execute_in_sandbox(
        code="c", data_json="{}", out_name="output.png",
        engine_name=ENGINE, tool_context=ctx, _client=fake,
    )

    assert out == PNG
    fake.agent_engines.sandboxes.create.assert_called_once()
    assert ctx.state[SANDBOX_NAME_KEY] == "sb-fresh"
    names = [c.kwargs["name"] for c in fake.agent_engines.sandboxes.execute_code.call_args_list]
    assert names == ["sb-stale", "sb-fresh"]


# ---------------------------------------------------------------------------
# execute_in_sandbox — non-stale errors are not retried
# ---------------------------------------------------------------------------


def test_execute_does_not_retry_on_non_stale_error():
    ctx = Ctx({SANDBOX_NAME_KEY: "sb-1"})
    empty = MagicMock()
    empty.outputs = []  # missing artifact -> SandboxError, which is NOT a stale signal
    fake = _fake_client(execute_return=empty)

    with pytest.raises(SandboxError):
        execute_in_sandbox(
            code="c", data_json="{}", out_name="output.png",
            engine_name=ENGINE, tool_context=ctx, _client=fake,
        )

    fake.agent_engines.sandboxes.create.assert_not_called()
    assert fake.agent_engines.sandboxes.execute_code.call_count == 1


# ---------------------------------------------------------------------------
# execute_in_sandbox — bounded retry (no infinite loop)
# ---------------------------------------------------------------------------


def test_execute_raises_when_stale_on_both_attempts():
    ctx = Ctx({SANDBOX_NAME_KEY: "sb-stale"})
    err = FakeAPIError(code=404, status="NOT_FOUND")
    fake = _fake_client(create_names=("sb-fresh",), execute_side_effect=[err, err])

    with pytest.raises(FakeAPIError):
        execute_in_sandbox(
            code="c", data_json="{}", out_name="output.png",
            engine_name=ENGINE, tool_context=ctx, _client=fake,
        )

    fake.agent_engines.sandboxes.create.assert_called_once()  # recreated once
    assert fake.agent_engines.sandboxes.execute_code.call_count == 2  # retried once, then gave up
