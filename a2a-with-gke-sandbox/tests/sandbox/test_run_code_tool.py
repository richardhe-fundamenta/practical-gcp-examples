from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from google.genai import types

from app.agent import run_code
from app.sandbox.client import SandboxError


def _set_sandbox_env(monkeypatch):
    monkeypatch.setenv("SANDBOX_API_URL", "http://router:8080")
    monkeypatch.setenv("SANDBOX_TEMPLATE", "python-sandbox-template")
    monkeypatch.setenv("SANDBOX_NAMESPACE", "default")
    monkeypatch.setenv("GKE_ENDPOINT", "10.0.0.2")
    monkeypatch.setenv("GKE_CA_CERT_PATH", "/tmp/ca.crt")


def _result(stdout="hello\n", files=None):
    return SimpleNamespace(stdout=stdout, files=files or [])


@patch("app.agent.run_python")
def test_run_code_passes_env_and_returns_stdout(mock_run, monkeypatch):
    _set_sandbox_env(monkeypatch)
    mock_run.return_value = _result("hello\n")
    tc = MagicMock()
    tc.user_content = None
    out = run_code(code="print('hello')", tool_context=tc)
    assert out == "hello\n"
    kwargs = mock_run.call_args.kwargs
    assert kwargs["api_url"] == "http://router:8080"
    assert kwargs["template"] == "python-sandbox-template"
    assert kwargs["endpoint"] == "10.0.0.2"
    assert kwargs["namespace"] == "default"
    assert kwargs["ca_cert_path"] == "/tmp/ca.crt"
    assert kwargs["files"] == []


@patch("app.agent.run_python")
def test_run_code_forwards_uploaded_files(mock_run, monkeypatch):
    _set_sandbox_env(monkeypatch)
    mock_run.return_value = _result("ok\n")
    blob = types.Blob(data=b"col\n1\n", mime_type="text/csv", display_name="data.csv")
    tc = MagicMock()
    tc.user_content = types.Content(role="user", parts=[types.Part(inline_data=blob)])
    run_code(code="print(open('data.csv').read())", tool_context=tc)
    assert mock_run.call_args.kwargs["files"] == [("data.csv", b"col\n1\n")]


@patch("app.agent.upload_and_sign", return_value="https://signed.example/chart.png")
@patch("app.agent.run_python")
def test_run_code_hosts_image_as_placeholder_not_raw_url(mock_run, mock_sign, monkeypatch):
    _set_sandbox_env(monkeypatch)
    mock_run.return_value = _result("done\n", files=[("chart.png", b"PNG")])
    tc = MagicMock()
    tc.user_content = None
    tc.state = {}
    out = run_code(code="...", tool_context=tc)
    mock_sign.assert_called_once_with(b"PNG", "chart.png", "image/png")
    tc.save_artifact.assert_not_called()
    # The raw signed URL is NOT exposed to the model — a placeholder token is.
    assert "https://signed.example/chart.png" not in out
    assert "{{chart:" in out
    assert "send_a2ui_json_to_client" in out
    # The placeholder -> real URL mapping is stored in state for the converter to substitute.
    url_map = tc.state["a2ui_url_map"]
    assert list(url_map.values()) == ["https://signed.example/chart.png"]
    assert next(iter(url_map)).startswith("{{chart:")


@patch("app.agent.run_python")
def test_run_code_saves_nonimage_files_as_artifacts(mock_run, monkeypatch):
    _set_sandbox_env(monkeypatch)
    mock_run.return_value = _result("done\n", files=[("report.csv", b"a,b\n1,2\n")])
    tc = MagicMock()
    tc.user_content = None
    out = run_code(code="...", tool_context=tc)
    assert "report.csv" in out  # attachment
    name, part = tc.save_artifact.call_args.args
    assert name == "report.csv"
    assert part.inline_data.data == b"a,b\n1,2\n"


@patch("app.agent.run_python")
def test_run_code_retries_then_caps_on_error(mock_run, monkeypatch):
    _set_sandbox_env(monkeypatch)
    mock_run.side_effect = SandboxError("boom")
    tc = MagicMock()
    tc.user_content = None
    tc.invocation_id = "inv1"
    tc.state = {}

    first = run_code(code="bad", tool_context=tc)
    assert "attempt 1/3" in first and "call run_code again" in first

    second = run_code(code="bad", tool_context=tc)
    assert "attempt 2/3" in second

    third = run_code(code="bad", tool_context=tc)
    assert "failed after 3 attempts" in third and "do not retry" in third
