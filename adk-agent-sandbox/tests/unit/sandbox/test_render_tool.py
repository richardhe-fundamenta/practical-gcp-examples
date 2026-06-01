import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from app.sandbox import render_tool


def _settings():
    s = MagicMock()
    s.agent_engine_name = "projects/p/locations/us-central1/reasoningEngines/r"
    return s


def _ctx(rows):
    c = MagicMock()
    c.state = {} if rows is None else {"validated_rows": rows}
    c.save_artifact = AsyncMock(return_value=1)
    return c


def test_render_ok_saves_image_artifact_from_stored_rows():
    ctx = _ctx([{"a": 1}])
    with patch.object(render_tool, "get_settings", return_value=_settings()), \
         patch.object(render_tool, "execute_in_sandbox", return_value=b"\x89PNG\r\n") as eis:
        out = asyncio.run(render_tool.render_chart(code="...", tool_context=ctx))
        assert out["status"] == "ok"
        assert out["artifact"] == "chart.png"
        # PNG is saved as an image/png artifact carrying the sandbox bytes
        ctx.save_artifact.assert_awaited_once()
        kwargs = ctx.save_artifact.await_args.kwargs
        assert kwargs["filename"] == "chart.png"
        part = kwargs["artifact"]
        assert part.inline_data.mime_type == "image/png"
        assert part.inline_data.data == b"\x89PNG\r\n"
        # data.json sent to the sandbox is built from the stored validated rows,
        # and the per-session lifecycle gets the host engine + tool_context.
        sandbox_kwargs = eis.call_args.kwargs
        assert '"rows"' in sandbox_kwargs["data_json"]
        assert '"a"' in sandbox_kwargs["data_json"]
        assert sandbox_kwargs["engine_name"] == "projects/p/locations/us-central1/reasoningEngines/r"
        assert sandbox_kwargs["tool_context"] is ctx
        # Stashes a pointer to the saved artifact so the after_agent_callback can return it
        # as an inline Part (so Gemini Enterprise renders it inline).
        from app.sandbox.render_tool import PENDING_CHART_KEY
        assert ctx.state[PENDING_CHART_KEY] == {"filename": "chart.png", "version": 1}


def test_render_error_returns_error_and_saves_nothing():
    from app.sandbox.client import SandboxError
    ctx = _ctx([{"a": 1}])
    with patch.object(render_tool, "get_settings", return_value=_settings()), \
         patch.object(render_tool, "execute_in_sandbox", side_effect=SandboxError("no output.png")):
        out = asyncio.run(render_tool.render_chart(code="boom", tool_context=ctx))
        assert out["status"] == "error"
        assert "no output.png" in out["error"]
        ctx.save_artifact.assert_not_awaited()


def test_render_refuses_without_validated_rows():
    """No successful query -> no data to chart -> refuse (prevents fabrication)."""
    ctx = _ctx(None)
    with patch.object(render_tool, "get_settings", return_value=_settings()), \
         patch.object(render_tool, "execute_in_sandbox") as eis:
        out = asyncio.run(render_tool.render_chart(code="...", tool_context=ctx))
        assert out["status"] == "error"
        assert "No validated query results" in out["error"]
        eis.assert_not_called()
        ctx.save_artifact.assert_not_awaited()
