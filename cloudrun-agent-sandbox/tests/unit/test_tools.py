import subprocess
from unittest.mock import MagicMock, patch

from app.tools import execute_python_code, execute_sandbox_command


@patch("shutil.which")
def test_execute_python_code_local_fallback(mock_which: MagicMock) -> None:
    mock_which.return_value = None
    # Test local fallback execution of simple print
    code = "print('hello from local fallback')"
    res = execute_python_code(code, allow_network=False)

    assert res["status"] == "success"
    assert "hello from local fallback" in res["stdout"]
    assert res["returncode"] == 0
    assert not res["sandboxed"]


@patch("shutil.which")
@patch("subprocess.run")
def test_execute_python_code_with_sandbox(
    mock_run: MagicMock, mock_which: MagicMock
) -> None:
    mock_which.return_value = "/usr/bin/sandbox"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "hello from sandbox"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    code = "print('hello')"
    res = execute_python_code(code, allow_network=False)

    assert res["status"] == "success"
    assert res["stdout"] == "hello from sandbox"
    assert res["sandboxed"]

    # Assert sandbox was called without egress
    args, _ = mock_run.call_args
    cmd = args[0]
    assert "sandbox" in cmd[0]
    assert cmd[1] == "do"
    assert "--allow-egress" not in cmd


@patch("shutil.which")
@patch("subprocess.run")
def test_execute_python_code_with_sandbox_and_network(
    mock_run: MagicMock, mock_which: MagicMock
) -> None:
    mock_which.return_value = "/usr/bin/sandbox"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "fetched content"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    code = "import urllib.request; print(urllib.request.urlopen('http://example.com').read())"
    res = execute_python_code(code, allow_network=True)

    assert res["status"] == "success"
    assert res["sandboxed"]

    # Assert sandbox was called with egress
    args, _ = mock_run.call_args
    cmd = args[0]
    assert "sandbox" in cmd[0]
    assert cmd[1] == "do"
    assert "--allow-egress" in cmd


@patch("shutil.which")
@patch("subprocess.run")
@patch.dict("os.environ", {"K_SERVICE": "my-service"})
def test_execute_python_code_production_no_sandbox(
    mock_run: MagicMock, mock_which: MagicMock
) -> None:
    mock_which.return_value = None

    code = "print('hello')"
    res = execute_python_code(code, allow_network=False)

    assert res["status"] == "error"
    assert "Sandbox execution is required in production" in res["stderr"]
    assert not res["sandboxed"]
    mock_run.assert_not_called()


@patch("shutil.which")
@patch("subprocess.run")
def test_execute_python_code_timeout(
    mock_run: MagicMock, mock_which: MagicMock
) -> None:
    mock_which.return_value = None
    mock_run.side_effect = subprocess.TimeoutExpired(cmd=["python"], timeout=10.0)

    code = "print('hello')"
    res = execute_python_code(code, allow_network=False)

    assert res["status"] == "error"
    assert (
        "Execution timed out after 10 seconds. Check for infinite loops or blockages."
        in res["stderr"]
    )
    assert res["returncode"] == -1
    assert not res["sandboxed"]


@patch("shutil.which")
@patch("subprocess.run")
@patch("os.path.exists")
def test_execute_python_code_first_run_export(
    mock_exists: MagicMock, mock_run: MagicMock, mock_which: MagicMock
) -> None:
    mock_which.return_value = "/usr/bin/sandbox"
    mock_exists.return_value = False  # No pre-existing state tar

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "first execution"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    res = execute_python_code("print('hello')", allow_network=False)

    assert res["status"] == "success"
    assert res["sandboxed"]

    args, _ = mock_run.call_args
    cmd = args[0]
    assert "--write" in cmd
    assert any(c.startswith("--export-tar=") and "sandbox_state_" in c for c in cmd)
    assert not any(c.startswith("--import-tar=") for c in cmd)


@patch("shutil.which")
@patch("subprocess.run")
@patch("os.path.exists")
def test_execute_python_code_subsequent_run_import_export(
    mock_exists: MagicMock, mock_run: MagicMock, mock_which: MagicMock
) -> None:
    mock_which.return_value = "/usr/bin/sandbox"
    mock_exists.return_value = True  # Pre-existing state tar exists

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "stateful execution"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    res = execute_python_code("print('hello')", allow_network=False)

    assert res["status"] == "success"
    assert res["sandboxed"]

    args, _ = mock_run.call_args
    cmd = args[0]
    assert "--write" in cmd
    assert any(c.startswith("--import-tar=") and "sandbox_state_" in c for c in cmd)
    assert any(c.startswith("--export-tar=") and "sandbox_state_" in c for c in cmd)


def test_execute_python_code_routes_streams() -> None:
    import sys

    code = "import sys; print('hello-stdout'); print('hello-stderr', file=sys.stderr)"
    with (
        patch.object(sys.stdout, "write") as mock_stdout_write,
        patch.object(sys.stderr, "write") as mock_stderr_write,
    ):
        result = execute_python_code(code)
        assert result["status"] == "success"
        assert "hello-stdout" in result["stdout"]
        assert "hello-stderr" in result["stderr"]
        # Verify sys.stdout and sys.stderr received the output
        mock_stdout_write.assert_any_call("hello-stdout\n")
        mock_stderr_write.assert_any_call("hello-stderr\n")


def test_execute_sandbox_command_formats_run():
    with (
        patch("shutil.which", return_value="/usr/local/gcp/bin/sandbox"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="out", stderr="")

        # Test running detached
        execute_sandbox_command(
            command=["/bin/sleep", "10m"],
            detach=True,
            sandbox_name="my-bg-sandbox",
            write=True,
            mounts=["type=bind,source=/tmp/default_session/vol,destination=/mnt/vol"],
        )

        expected_cmd = [
            "/usr/local/gcp/bin/sandbox",
            "run",
            "my-bg-sandbox",
            "--detach",
            "--write",
            "--mount",
            "type=bind,source=/tmp/default_session/vol,destination=/mnt/vol",
            "--",
            "/bin/sleep",
            "10m",
        ]
        mock_run.assert_called_with(
            expected_cmd, capture_output=True, text=True, timeout=10
        )


def test_execute_sandbox_command_formats_exec():
    with (
        patch("shutil.which", return_value="/usr/local/gcp/bin/sandbox"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="out", stderr="")

        # Test executing inside existing named sandbox
        execute_sandbox_command(
            command=["/bin/echo", "hello"], exec_on_sandbox="my-bg-sandbox"
        )

        expected_cmd = [
            "/usr/local/gcp/bin/sandbox",
            "exec",
            "my-bg-sandbox",
            "--",
            "/bin/echo",
            "hello",
        ]
        mock_run.assert_called_with(
            expected_cmd, capture_output=True, text=True, timeout=10
        )


def test_execute_sandbox_command_formats_tar():
    with (
        patch("shutil.which", return_value="/usr/local/gcp/bin/sandbox"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Test creating a tar snapshot
        execute_sandbox_command(
            tar_sandbox="my-bg-sandbox", tar_file="/tmp/default_session/snapshot.tar"
        )

        expected_cmd = [
            "/usr/local/gcp/bin/sandbox",
            "tar",
            "my-bg-sandbox",
            "--file=/tmp/default_session/snapshot.tar",
        ]
        mock_run.assert_called_with(
            expected_cmd, capture_output=True, text=True, timeout=10
        )


def test_execute_sandbox_command_tar_requires_file():
    # 1. With sandbox available
    with patch("shutil.which", return_value="/usr/local/gcp/bin/sandbox"):
        res = execute_sandbox_command(tar_sandbox="my-bg-sandbox")
        assert res["status"] == "error"
        assert "tar_file is required when tar_sandbox is set." in res["stderr"]
        assert res["sandboxed"]

    # 2. Without sandbox available (local fallback)
    with patch("shutil.which", return_value=None):
        res = execute_sandbox_command(tar_sandbox="my-bg-sandbox")
        assert res["status"] == "error"
        assert "tar_file is required when tar_sandbox is set." in res["stderr"]
        assert not res["sandboxed"]


@patch("shutil.which")
@patch("subprocess.run")
def test_execute_sandbox_command_local_fallback(
    mock_run: MagicMock, mock_which: MagicMock
) -> None:
    mock_which.return_value = None

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "hello from local"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    cmd = ["echo", "hello"]
    res = execute_sandbox_command(command=cmd)

    assert res["status"] == "success"
    assert res["stdout"] == "hello from local"
    assert not res["sandboxed"]
    mock_run.assert_called_with(cmd, capture_output=True, text=True, timeout=10)


@patch("shutil.which")
@patch("subprocess.run")
def test_execute_sandbox_command_routes_streams(
    mock_run: MagicMock, mock_which: MagicMock
) -> None:
    import sys

    mock_which.return_value = None

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "hello-stdout\n"
    mock_result.stderr = "hello-stderr\n"
    mock_run.return_value = mock_result

    with (
        patch.object(sys.stdout, "write") as mock_stdout_write,
        patch.object(sys.stderr, "write") as mock_stderr_write,
    ):
        result = execute_sandbox_command(command=["echo", "hello"])
        assert result["status"] == "success"
        assert "hello-stdout" in result["stdout"]
        assert "hello-stderr" in result["stderr"]
        # Verify sys.stdout and sys.stderr received the output
        mock_stdout_write.assert_any_call("hello-stdout\n")
        mock_stderr_write.assert_any_call("hello-stderr\n")


def test_execute_sandbox_command_mount_restriction() -> None:
    # Test mounting directory outside the allowed session directory /tmp/default_session
    res = execute_sandbox_command(
        command=["ls"],
        mounts=["type=bind,source=/tmp/other_session,destination=/mnt/val"],
    )
    assert res["status"] == "error"
    assert "Permission denied: Mount source path" in res["stderr"]


def test_execute_sandbox_command_tar_restriction() -> None:
    # Test generating tar snapshot outside the allowed session directory /tmp/default_session
    res = execute_sandbox_command(
        tar_sandbox="my-sandbox", tar_file="/tmp/other_session/snapshot.tar"
    )
    assert res["status"] == "error"
    assert "Permission denied: tar_file path" in res["stderr"]
