from unittest.mock import patch, MagicMock
from app.sandbox import render_tool


def _settings():
    s = MagicMock()
    s.sandbox_resource_name = "projects/p/locations/us-central1/reasoningEngines/r/sandboxEnvironments/s"
    return s


def test_render_ok_returns_base64():
    with patch.object(render_tool, "get_settings", return_value=_settings()), \
         patch.object(render_tool, "run_in_sandbox", return_value=b"\x89PNG\r\n"):
        out = render_tool.render_chart(code="...", data_json="{}")
        assert out["status"] == "ok"
        import base64
        assert base64.b64decode(out["png_base64"]) == b"\x89PNG\r\n"


def test_render_error_returns_error_dict():
    from app.sandbox.client import SandboxError
    with patch.object(render_tool, "get_settings", return_value=_settings()), \
         patch.object(render_tool, "run_in_sandbox", side_effect=SandboxError("no output.png")):
        out = render_tool.render_chart(code="boom", data_json="{}")
        assert out["status"] == "error"
        assert "no output.png" in out["error"]
