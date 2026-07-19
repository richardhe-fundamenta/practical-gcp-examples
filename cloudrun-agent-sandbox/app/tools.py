import logging
import os
import shutil
import subprocess
import sys
import tempfile

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)

# =====================================================================
# Private Helper Functions
# =====================================================================


def _get_session_directory(
    tool_context: ToolContext | None = None,
) -> tuple[str, str, str]:
    """Helper to determine the session ID, parent sessions directory, and canonical allowed session directory path."""
    session_id = "default_session"
    if tool_context:
        if getattr(tool_context, "session", None) and getattr(
            tool_context.session, "id", None
        ):
            session_id = tool_context.session.id
        elif tool_context.state:
            session_id = tool_context.state.get("session_id", "default_session")

    in_production = "K_SERVICE" in os.environ
    sessions_dir = (
        "/sessions" if (os.path.isdir("/sessions") or in_production) else "/tmp"
    )

    allowed_prefix = os.path.realpath(os.path.join(sessions_dir, session_id))
    os.makedirs(allowed_prefix, exist_ok=True)
    # Auto-create the persistent directory on the host container FUSE FUSE bucket FUSE mount
    os.makedirs(os.path.join(allowed_prefix, "persistent"), exist_ok=True)

    return session_id, sessions_dir, allowed_prefix


def _get_sandbox_path() -> str:
    """Resolves and returns the path to the sandbox binary.
    Raises FileNotFoundError if sandbox is not available.
    """
    sandbox_path = shutil.which("sandbox")
    if not sandbox_path and os.path.exists("/usr/local/gcp/bin/sandbox"):
        sandbox_path = "/usr/local/gcp/bin/sandbox"
    if not sandbox_path:
        raise FileNotFoundError(
            "Sandbox launcher binary 'sandbox' was not found on PATH or at '/usr/local/gcp/bin/sandbox'. "
            "Cloud Run Sandbox execution requires the sandbox binary."
        )
    return sandbox_path


def _resolve_session_path(
    path: str | None, tool_context: ToolContext | None, label: str
) -> str:
    """Resolves and returns the canonical absolute path of a session file.
    If path is relative or just a filename, resolves it relative to the session directory.
    If absolute, validates that it lies within the allowed session directory.
    Raises PermissionError if the path is invalid or attempts traversal.
    """
    if not path:
        return ""
    session_id, sessions_dir, allowed_prefix = _get_session_directory(tool_context)
    # Check if the path is a simple filename (no directory separators)
    if not os.path.isabs(path) and not os.sep in path:
        resolved_path = os.path.realpath(os.path.join(allowed_prefix, path))
    else:
        # If absolute or relative path with separators, resolve and validate it
        if os.path.isabs(path):
            resolved_path = os.path.realpath(path)
        else:
            resolved_path = os.path.realpath(os.path.join(allowed_prefix, path))
            
        if not (
            resolved_path == allowed_prefix
            or resolved_path.startswith(allowed_prefix + os.sep)
        ):
            raise PermissionError(
                f"Permission denied: {label} '{path}' is not within "
                f"your allowed session directory '{sessions_dir}/{session_id}'."
            )
    return resolved_path


def _get_scoped_name(
    sandbox_name: str, tool_context: ToolContext | None = None
) -> str:
    """Helper to prefix a background sandbox name with the session ID."""
    session_id, _, _ = _get_session_directory(tool_context)
    return f"{session_id}-{sandbox_name}"


def _run_sandbox_subprocess(cmd: list[str], timeout: int = 30) -> dict:
    """Helper to run a subprocess command under the sandbox,
    capture outputs, and return a standardized result dictionary.
    """
    logger.info(f"Executing command: {cmd}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if res.stdout:
            sys.stdout.write(res.stdout)
            sys.stdout.flush()
        if res.stderr:
            sys.stderr.write(res.stderr)
            sys.stderr.flush()
        logger.info(f"Command execution completed. returncode={res.returncode}")
        return {
            "status": "success" if res.returncode == 0 else "error",
            "stdout": res.stdout,
            "stderr": res.stderr,
            "returncode": res.returncode,
            "sandboxed": True,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "stdout": "",
            "stderr": f"Execution timed out after {timeout} seconds.",
            "returncode": -1,
            "sandboxed": True,
        }


# =====================================================================
# Public Tool Functions
# =====================================================================


def run_python_script(
    code: str,
    write: bool = False,
    sync_tar: str | None = None,
    env: dict[str, str] | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Executes a Python script inside the secure Cloud Run sandbox.

    Args:
        code: The Python code string to execute.
        write: Set to True to allow writing to the sandbox overlay filesystem.
        sync_tar: The sandbox state tar file path to import/export.
        env: Environment variables to set for execution.
        tool_context: The ADK tool context.
    """
    logger.info("Starting run_python_script tool execution.")
    temp_file_path = None
    try:
        session_id, sessions_dir, allowed_prefix = _get_session_directory(tool_context)
        host_persistent = os.path.join(allowed_prefix, "persistent")
        default_mount = f"type=bind,source={host_persistent},destination=/mnt/persistent"

        if sync_tar:
            sync_tar = _resolve_session_path(sync_tar, tool_context, "sync_tar path")

        # Create a temporary file to write the python code
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            temp_file_path = f.name
            logger.info(f"Writing user Python code to temporary file: {temp_file_path}")
            f.write(code)

        sandbox_path = _get_sandbox_path()

        cmd = [sandbox_path, "do"]
        if write:
            cmd.append("--write")
        if sync_tar:
            cmd.append(f"--sync-tar={sync_tar}")
        cmd.extend(["--mount", default_mount])
        if env:
            for k, v in env.items():
                cmd.extend(["--env", f"{k}={v}"])
        cmd.extend(["--", sys.executable, temp_file_path])

        return _run_sandbox_subprocess(cmd)
    except Exception as e:
        logger.error(
            f"Error occurred during sandbox tool execution: {e}", exc_info=True
        )
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "sandboxed": True,
        }
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            logger.info(f"Removing temporary execution file: {temp_file_path}")
            os.remove(temp_file_path)


def run_sandbox_command(
    command: list[str],
    write: bool = False,
    sync_tar: str | None = None,
    env: dict[str, str] | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Runs a command synchronously inside a sandbox do execution.

    Args:
        command: List of command arguments to run.
        write: Set to True to allow writing to the sandbox overlay.
        sync_tar: The sandbox state tar file path to import/export.
        env: Environment variables to set.
        tool_context: The ADK tool context.
    """
    logger.info("Starting run_sandbox_command tool execution.")
    try:
        sandbox_path = _get_sandbox_path()

        session_id, sessions_dir, allowed_prefix = _get_session_directory(tool_context)
        host_persistent = os.path.join(allowed_prefix, "persistent")
        default_mount = f"type=bind,source={host_persistent},destination=/mnt/persistent"

        if sync_tar:
            sync_tar = _resolve_session_path(sync_tar, tool_context, "sync_tar path")

        cmd = [sandbox_path, "do"]
        if write:
            cmd.append("--write")
        if sync_tar:
            cmd.append(f"--sync-tar={sync_tar}")
        cmd.extend(["--mount", default_mount])
        if env:
            for k, v in env.items():
                cmd.extend(["--env", f"{k}={v}"])
        cmd.append("--")
        cmd.extend(command)

        return _run_sandbox_subprocess(cmd)
    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "sandboxed": True,
        }


def start_background_sandbox(
    sandbox_name: str,
    command: list[str],
    write: bool = False,
    env: dict[str, str] | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Starts a background sandbox session with detach flag.

    Args:
        sandbox_name: Unique name for the sandbox session.
        command: List of command arguments to start.
        write: Set to True to allow writing to the sandbox overlay.
        env: Environment variables to set.
        tool_context: The ADK tool context.
    """
    logger.info(f"Starting start_background_sandbox tool execution for name={sandbox_name}.")
    try:
        sandbox_path = _get_sandbox_path()

        session_id, sessions_dir, allowed_prefix = _get_session_directory(tool_context)
        host_persistent = os.path.join(allowed_prefix, "persistent")
        default_mount = f"type=bind,source={host_persistent},destination=/mnt/persistent"

        scoped_name = _get_scoped_name(sandbox_name, tool_context)

        cmd = [sandbox_path, "run", scoped_name, "--detach"]
        if write:
            cmd.append("--write")
        cmd.extend(["--mount", default_mount])
        if env:
            for k, v in env.items():
                cmd.extend(["--env", f"{k}={v}"])
        cmd.append("--")
        cmd.extend(command)

        return _run_sandbox_subprocess(cmd)
    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "sandboxed": True,
        }


def execute_in_background_sandbox(
    sandbox_name: str,
    command: list[str],
    tool_context: ToolContext | None = None,
) -> dict:
    """Executes a command inside an active background sandbox container.

    Args:
        sandbox_name: Name of the running background sandbox.
        command: List of command arguments to execute.
        tool_context: The ADK tool context.
    """
    logger.info(f"Starting execute_in_background_sandbox tool execution on name={sandbox_name}.")
    try:
        sandbox_path = _get_sandbox_path()
        scoped_name = _get_scoped_name(sandbox_name, tool_context)
        cmd = [sandbox_path, "exec", scoped_name, "--", *command]
        return _run_sandbox_subprocess(cmd)
    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "sandboxed": True,
        }



def stop_background_sandbox(
    sandbox_name: str,
    tool_context: ToolContext | None = None,
) -> dict:
    """Stops and deletes a background sandbox session.

    Args:
        sandbox_name: Name of the running background sandbox.
        tool_context: The ADK tool context.
    """
    logger.info(f"Starting stop_background_sandbox tool execution for name={sandbox_name}.")
    try:
        sandbox_path = _get_sandbox_path()
        scoped_name = _get_scoped_name(sandbox_name, tool_context)
        cmd = [sandbox_path, "delete", scoped_name, "--force"]
        return _run_sandbox_subprocess(cmd, timeout=60)
    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "sandboxed": True,
        }
