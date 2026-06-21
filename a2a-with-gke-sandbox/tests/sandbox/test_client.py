from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
from app.sandbox import client as sbx


def _fake_client(stdout="hi\n", exit_code=0, stderr=""):
    sandbox = MagicMock()
    sandbox.commands.run.return_value = MagicMock(
        stdout=stdout, stderr=stderr, exit_code=exit_code
    )
    sandbox.files.list.return_value = []  # no generated files by default
    c = MagicMock()
    c.create_sandbox.return_value = sandbox
    return c, sandbox


@patch("app.sandbox.client.install_default_k8s_config")
def test_run_python_returns_stdout_and_terminates(_auth):
    c, sandbox = _fake_client("42\n")
    out = sbx.run_python(
        "print(40+2)", api_url="http://router:8080", template="python-sandbox-template",
        namespace="default", endpoint="10.0.0.2", ca_cert_path="/tmp/ca.crt", _client=c,
    )
    assert out.stdout == "42\n"
    assert out.files == []
    c.create_sandbox.assert_called_once_with(
        template="python-sandbox-template", namespace="default"
    )
    # Code is written by basename and run relative to the runtime working dir (no shell).
    sandbox.files.write.assert_called_once_with("main.py", "print(40+2)")
    sandbox.commands.run.assert_called_once_with("python3 main.py")
    sandbox.terminate.assert_called_once()


@patch("app.sandbox.client.install_default_k8s_config")
def test_run_python_returns_generated_files(_auth):
    c, sandbox = _fake_client("done\n")
    # files.list is called twice: a pristine-image baseline (pyproject.toml ships in the
    # image), then post-run with main.py, the input, and a generated chart added.
    sandbox.files.list.side_effect = [
        [SimpleNamespace(name="pyproject.toml", size=20)],
        [
            SimpleNamespace(name="pyproject.toml", size=20),
            SimpleNamespace(name="main.py", size=10),
            SimpleNamespace(name="data.csv", size=6),
            SimpleNamespace(name="chart.png", size=3),
        ],
    ]
    sandbox.files.read.return_value = b"PNG"
    out = sbx.run_python(
        "import matplotlib", api_url="u", template="t", namespace="n", endpoint="e",
        files=[("data.csv", b"col\n1\n")], _client=c,
    )
    # Only the generated file is returned — baseline image files, main.py and the input excluded.
    assert out.files == [("chart.png", b"PNG")]
    sandbox.files.read.assert_called_once_with("chart.png")


@patch("app.sandbox.client.install_default_k8s_config")
def test_run_python_writes_uploaded_files_before_main(_auth):
    c, sandbox = _fake_client("ok\n")
    out = sbx.run_python(
        "print(open('data.csv').read())", api_url="http://router:8080", template="t",
        namespace="default", endpoint="e", files=[("data.csv", b"col\n1\n")], _client=c,
    )
    assert out.stdout == "ok\n"
    written = [tuple(call.args) for call in sandbox.files.write.call_args_list]
    assert ("data.csv", b"col\n1\n") in written
    assert ("main.py", "print(open('data.csv').read())") in written


@patch("app.sandbox.client.install_default_k8s_config")
def test_run_python_raises_on_nonzero_exit(_auth):
    c, sandbox = _fake_client(stdout="", exit_code=1, stderr="Traceback: boom")
    with pytest.raises(sbx.SandboxError, match="exit 1.*boom"):
        sbx.run_python(
            "raise SystemExit(1)", api_url="http://router:8080", template="t",
            namespace="default", endpoint="e", _client=c,
        )
    sandbox.terminate.assert_called_once()


@patch("app.sandbox.client.install_default_k8s_config")
def test_run_python_terminates_on_error(_auth):
    c, sandbox = _fake_client()
    sandbox.commands.run.side_effect = RuntimeError("boom")
    with pytest.raises(sbx.SandboxError):
        sbx.run_python(
            "print(1)", api_url="http://router:8080", template="t",
            namespace="default", endpoint="e", ca_cert_path="/tmp/ca.crt", _client=c,
        )
    sandbox.terminate.assert_called_once()


@patch("app.sandbox.client.install_default_k8s_config")
def test_run_python_wraps_create_sandbox_error(_auth):
    c, sandbox = _fake_client()
    c.create_sandbox.side_effect = RuntimeError("no quota")
    with pytest.raises(sbx.SandboxError, match="sandbox creation failed"):
        sbx.run_python(
            "print(1)", api_url="http://router:8080", template="t",
            namespace="default", endpoint="e", ca_cert_path="/tmp/ca.crt", _client=c,
        )
    sandbox.terminate.assert_not_called()
