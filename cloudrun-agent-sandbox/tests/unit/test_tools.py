import os
import subprocess
from unittest.mock import MagicMock, patch
import pytest

from app.tools import (
    _get_sandbox_path,
    _get_session_directory,
    run_python_script,
    run_sandbox_command,
    start_background_sandbox,
    execute_in_background_sandbox,
    stop_background_sandbox,
)


# =====================================================================
# Private Helper Tests
# =====================================================================


@patch("shutil.which")
@patch("os.path.exists")
def test_get_sandbox_path_found(mock_exists: MagicMock, mock_which: MagicMock) -> None:
    mock_which.return_value = "/usr/bin/sandbox"
    assert _get_sandbox_path() == "/usr/bin/sandbox"

    mock_which.return_value = None
    mock_exists.return_value = True
    assert _get_sandbox_path() == "/usr/local/gcp/bin/sandbox"


@patch("shutil.which")
@patch("os.path.exists")
def test_get_sandbox_path_not_found(mock_exists: MagicMock, mock_which: MagicMock) -> None:
    mock_which.return_value = None
    mock_exists.return_value = False
    with pytest.raises(FileNotFoundError):
        _get_sandbox_path()


def test_session_directory_creates_persistent_folder() -> None:
    allowed_prefix = _get_session_directory(None)[2]
    expected_path = os.path.join(allowed_prefix, "persistent")
    assert os.path.isdir(expected_path) is True


# =====================================================================
# Public Tool Tests (MOCKED Sandbox Environment)
# =====================================================================


@patch("app.tools._get_sandbox_path")
@patch("subprocess.run")
def test_run_python_script_sandbox_success(
    mock_run: MagicMock, mock_get_path: MagicMock
) -> None:
    mock_get_path.return_value = "/usr/bin/sandbox"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "hello from sandbox\n"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    res = run_python_script(code="print('hello')", tool_context=None)

    assert res["status"] == "success"
    assert res["stdout"] == "hello from sandbox\n"
    assert res["stderr"] == ""
    assert res["returncode"] == 0
    assert res["sandboxed"] is True

    args, _ = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "/usr/bin/sandbox"
    assert cmd[1] == "do"
    assert "--write" not in cmd
    assert "--allow-egress" not in cmd
    assert "--mount" in cmd
    mount_idx = cmd.index("--mount")
    allowed_prefix = _get_session_directory(None)[2]
    assert cmd[mount_idx + 1] == f"type=bind,source={allowed_prefix}/persistent,destination=/mnt/persistent"


@patch("app.tools._get_sandbox_path")
@patch("subprocess.run")
def test_run_python_script_sandbox_with_args(
    mock_run: MagicMock, mock_get_path: MagicMock
) -> None:
    mock_get_path.return_value = "/usr/bin/sandbox"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "sandbox run output\n"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    allowed_prefix = _get_session_directory(None)[2]
    sync_tar_path = f"{allowed_prefix}/state.tar"

    res = run_python_script(
        code="print('hello')",
        write=True,
        sync_tar=sync_tar_path,
        env={"FOO": "BAR"},
        tool_context=None,
    )

    assert res["status"] == "success"
    assert res["stdout"] == "sandbox run output\n"
    assert res["stderr"] == ""
    assert res["returncode"] == 0
    assert res["sandboxed"] is True

    args, _ = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "/usr/bin/sandbox"
    assert cmd[1] == "do"
    assert "--write" in cmd
    assert "--allow-egress" not in cmd
    assert f"--sync-tar={sync_tar_path}" in cmd
    env_idx = cmd.index("--env")
    assert cmd[env_idx + 1] == "FOO=BAR"
    assert "--mount" in cmd
    mount_idx = cmd.index("--mount")
    assert cmd[mount_idx + 1] == f"type=bind,source={allowed_prefix}/persistent,destination=/mnt/persistent"


@patch("app.tools._get_sandbox_path")
def test_run_python_script_sandbox_not_found(mock_get_path: MagicMock) -> None:
    mock_get_path.side_effect = FileNotFoundError("Sandbox launcher binary was not found.")

    res = run_python_script(code="print('hello')", tool_context=None)
    assert res["status"] == "error"
    assert "Sandbox launcher binary" in res["stderr"]
    assert res["returncode"] == -1


@patch("app.tools._get_sandbox_path")
@patch("subprocess.run")
def test_run_sandbox_command_sandboxed(
    mock_run: MagicMock, mock_get_path: MagicMock
) -> None:
    mock_get_path.return_value = "/usr/local/gcp/bin/sandbox"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "ls output"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    allowed_prefix = _get_session_directory(None)[2]
    sync_tar_path = f"{allowed_prefix}/state.tar"

    res = run_sandbox_command(
        command=["ls"],
        write=True,
        sync_tar=sync_tar_path,
        env={"MY_ENV": "VALUE"},
    )
    assert res["status"] == "success"
    assert res["stdout"] == "ls output"
    assert res["stderr"] == ""
    assert res["returncode"] == 0
    assert res["sandboxed"] is True

    expected_cmd = [
        "/usr/local/gcp/bin/sandbox",
        "do",
        "--write",
        f"--sync-tar={sync_tar_path}",
        "--mount",
        f"type=bind,source={allowed_prefix}/persistent,destination=/mnt/persistent",
        "--env",
        "MY_ENV=VALUE",
        "--",
        "ls",
    ]
    mock_run.assert_called_with(
        expected_cmd, capture_output=True, text=True, timeout=30
    )


@patch("app.tools._get_sandbox_path")
def test_run_python_script_sync_tar_restriction(mock_get_path: MagicMock) -> None:
    mock_get_path.return_value = "/usr/bin/sandbox"
    res = run_python_script(
        code="print('hello')",
        sync_tar="/tmp/unauthorized_dir/state.tar",
    )
    assert res["status"] == "error"
    assert "Permission denied: sync_tar path" in res["stderr"]
    assert res["stdout"] == ""
    assert res["returncode"] == -1


@patch("app.tools._get_sandbox_path")
def test_run_sandbox_command_sync_tar_restriction(mock_get_path: MagicMock) -> None:
    mock_get_path.return_value = "/usr/bin/sandbox"
    res = run_sandbox_command(
        command=["ls"],
        sync_tar="/tmp/unauthorized_dir/state.tar",
    )
    assert res["status"] == "error"
    assert "Permission denied: sync_tar path" in res["stderr"]
    assert res["stdout"] == ""
    assert res["returncode"] == -1


@patch("app.tools._get_sandbox_path")
@patch("subprocess.run")
def test_start_background_sandbox_sandboxed(
    mock_run: MagicMock, mock_get_path: MagicMock
) -> None:
    mock_get_path.return_value = "/usr/local/gcp/bin/sandbox"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "started detached"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    allowed_prefix = _get_session_directory(None)[2]

    res = start_background_sandbox(
        sandbox_name="test-bg",
        command=["sleep", "10"],
        write=True,
        env={"MY_ENV": "VALUE"},
    )
    assert res["status"] == "success"
    assert res["stdout"] == "started detached"
    assert res["stderr"] == ""
    assert res["returncode"] == 0
    assert res["sandboxed"] is True

    expected_cmd = [
        "/usr/local/gcp/bin/sandbox",
        "run",
        "default_session-test-bg",
        "--detach",
        "--write",
        "--mount",
        f"type=bind,source={allowed_prefix}/persistent,destination=/mnt/persistent",
        "--env",
        "MY_ENV=VALUE",
        "--",
        "sleep",
        "10",
    ]
    mock_run.assert_called_with(
        expected_cmd, capture_output=True, text=True, timeout=30
    )


@patch("app.tools._get_sandbox_path")
@patch("subprocess.run")
def test_execute_in_background_sandbox_sandboxed(
    mock_run: MagicMock, mock_get_path: MagicMock
) -> None:
    mock_get_path.return_value = "/usr/local/gcp/bin/sandbox"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "exec success"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    res = execute_in_background_sandbox(sandbox_name="test-bg", command=["ls"])
    assert res["status"] == "success"
    assert res["stdout"] == "exec success"
    assert res["stderr"] == ""
    assert res["returncode"] == 0
    assert res["sandboxed"] is True

    expected_cmd = ["/usr/local/gcp/bin/sandbox", "exec", "default_session-test-bg", "--", "ls"]
    mock_run.assert_called_with(
        expected_cmd, capture_output=True, text=True, timeout=30
    )



@patch("app.tools._get_sandbox_path")
@patch("subprocess.run")
def test_stop_background_sandbox_sandboxed(
    mock_run: MagicMock, mock_get_path: MagicMock
) -> None:
    mock_get_path.return_value = "/usr/local/gcp/bin/sandbox"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "delete success"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    res = stop_background_sandbox(sandbox_name="test-bg")
    assert res["status"] == "success"
    assert res["stdout"] == "delete success"
    assert res["stderr"] == ""
    assert res["returncode"] == 0
    assert res["sandboxed"] is True

    expected_cmd = ["/usr/local/gcp/bin/sandbox", "delete", "default_session-test-bg", "--force"]
    mock_run.assert_called_with(
        expected_cmd, capture_output=True, text=True, timeout=60
    )


@patch("app.tools._get_sandbox_path")
@patch("subprocess.run")
def test_run_python_script_relative_sync_tar(
    mock_run: MagicMock, mock_get_path: MagicMock
) -> None:
    mock_get_path.return_value = "/usr/bin/sandbox"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "relative success"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    res = run_python_script(
        code="print('hello')",
        sync_tar="relative_state.tar",
    )

    assert res["status"] == "success"
    
    allowed_prefix = _get_session_directory(None)[2]
    expected_path = os.path.realpath(os.path.join(allowed_prefix, "relative_state.tar"))
    
    args, _ = mock_run.call_args
    cmd = args[0]
    assert f"--sync-tar={expected_path}" in cmd
