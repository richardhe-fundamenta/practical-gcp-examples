from unittest.mock import patch, MagicMock
from app.sandbox import render_tool


def _settings():
    s = MagicMock()
    s.sandbox_resource_name = "projects/p/locations/us-central1/reasoningEngines/r/sandboxEnvironments/s"
    return s


def _ctx(rows):
    c = MagicMock()
    c.state = {} if rows is None else {"validated_rows": rows}
    return c


def test_render_ok_uses_stored_rows_and_returns_base64():
    with patch.object(render_tool, "get_settings", return_value=_settings()), \
         patch.object(render_tool, "run_in_sandbox", return_value=b"\x89PNG\r\n") as ris:
        out = render_tool.render_chart(code="...", tool_context=_ctx([{"a": 1}]))
        assert out["status"] == "ok"
        import base64
        assert base64.b64decode(out["png_base64"]) == b"\x89PNG\r\n"
        # The data.json sent to the sandbox is built from the stored validated rows,
        # not from anything the model supplied.
        _, kwargs = ris.call_args
        assert '"rows"' in kwargs["data_json"]
        assert '"a"' in kwargs["data_json"]


def test_render_error_returns_error_dict():
    from app.sandbox.client import SandboxError
    with patch.object(render_tool, "get_settings", return_value=_settings()), \
         patch.object(render_tool, "run_in_sandbox", side_effect=SandboxError("no output.png")):
        out = render_tool.render_chart(code="boom", tool_context=_ctx([{"a": 1}]))
        assert out["status"] == "error"
        assert "no output.png" in out["error"]


def test_render_refuses_without_validated_rows():
    """No successful query -> no data to chart -> refuse (prevents fabrication)."""
    with patch.object(render_tool, "get_settings", return_value=_settings()), \
         patch.object(render_tool, "run_in_sandbox") as ris:
        out = render_tool.render_chart(code="...", tool_context=_ctx(None))
        assert out["status"] == "error"
        assert "No validated query results" in out["error"]
        ris.assert_not_called()
