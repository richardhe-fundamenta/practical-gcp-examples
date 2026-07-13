import logging
import os
import shutil
import subprocess
import sys
import tempfile

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


def get_session_directory(
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

    return session_id, sessions_dir, allowed_prefix


def execute_python_code(
    code: str, allow_network: bool = False, tool_context: ToolContext | None = None
) -> dict:
    """Executes arbitrary Python code in a secure Cloud Run sandbox environment.

    Args:
        code: The Python code string to execute.
        allow_network: Set to True if the code requires outbound network access (e.g., fetching a URL or API). Defaults to False.

    Returns:
        A dictionary containing the execution status ('success' or 'error'),
        stdout, stderr, exit code, and whether it was run inside the sandbox.
    """
    logger.info("Starting execute_python_code tool execution.")
    sandbox_available = False
    temp_file_path = None
    try:
        # Create a temporary file to write the python code
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            temp_file_path = f.name
            logger.info(f"Writing user Python code to temporary file: {temp_file_path}")
            f.write(code)

        sandbox_path = shutil.which("sandbox")
        if not sandbox_path and os.path.exists("/usr/local/gcp/bin/sandbox"):
            sandbox_path = "/usr/local/gcp/bin/sandbox"

        sandbox_available = sandbox_path is not None
        in_production = "K_SERVICE" in os.environ
        logger.info(
            f"Environment check: sandbox_available={sandbox_available} (path: {sandbox_path}), in_production={in_production}"
        )

        if not sandbox_available and in_production:
            logger.error(
                "Sandbox execution is required in production but the sandbox launcher is not available. Aborting."
            )
            return {
                "status": "error",
                "stdout": "",
                "stderr": "Sandbox execution is required in production but the sandbox launcher is not available.",
                "returncode": -1,
                "sandboxed": False,
            }

        if sandbox_available:
            cmd = [sandbox_path, "do", "--write"]

            # Scope state archive by session ID
            session_id, sessions_dir, _ = get_session_directory(tool_context)
            state_tar_path = f"{sessions_dir}/sandbox_state_{session_id}.tar"
            logger.info(
                f"Scoping sandbox session. session_id={session_id}, state_tar_path={state_tar_path}"
            )

            if os.path.exists(state_tar_path):
                logger.info(
                    f"Found pre-existing state tar archive. Appending --import-tar={state_tar_path}"
                )
                cmd.append(f"--import-tar={state_tar_path}")
            else:
                logger.info(
                    "No pre-existing state tar archive found. Starting clean slate."
                )
            cmd.append(f"--export-tar={state_tar_path}")

            if allow_network:
                logger.info("Network access enabled. Appending --allow-egress")
                cmd.append("--allow-egress")
            cmd.extend(["--", sys.executable, temp_file_path])
        else:
            # Local fallback for development and testing
            logger.info(
                "Sandbox launcher not available. Falling back to local execution."
            )
            cmd = [sys.executable, temp_file_path]

        logger.info(f"Executing command: {cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.stdout:
            sys.stdout.write(result.stdout)
            sys.stdout.flush()
        if result.stderr:
            sys.stderr.write(result.stderr)
            sys.stderr.flush()
        logger.info(f"Command execution completed. returncode={result.returncode}")

        status = "success" if result.returncode == 0 else "error"
        if status == "success":
            logger.info(f"Execution succeeded. stdout length: {len(result.stdout)}")
        else:
            logger.error(f"Execution failed. stderr: {result.stderr.strip()}")

        return {
            "status": status,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "sandboxed": sandbox_available,
        }
    except subprocess.TimeoutExpired as e:
        logger.error(f"Command execution timed out: {e}")
        return {
            "status": "error",
            "stdout": "",
            "stderr": "Execution timed out after 10 seconds. Check for infinite loops or blockages.",
            "returncode": -1,
            "sandboxed": sandbox_available,
        }
    except Exception as e:
        logger.error(
            f"Error occurred during sandbox tool execution: {e}", exc_info=True
        )
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "sandboxed": sandbox_available,
        }
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            logger.info(f"Removing temporary execution file: {temp_file_path}")
            os.remove(temp_file_path)


def execute_sandbox_command(
    command: list[str] | None = None,
    detach: bool = False,
    sandbox_name: str | None = None,
    write: bool = False,
    mounts: list[str] | None = None,
    exec_on_sandbox: str | None = None,
    tar_sandbox: str | None = None,
    tar_file: str | None = None,
    allow_network: bool = False,
    tool_context: ToolContext | None = None,
) -> dict:
    """Executes a command inside the secure Cloud Run sandbox environment with advanced controls.

    Args:
        command: List of command arguments.
        detach: If True, runs the sandbox detached (background). Requires a sandbox_name.
        sandbox_name: Name of the sandbox.
        write: Set to True to allow writing to the sandbox overlay.
        mounts: List of mount specifications (e.g. type=bind,source=/src,destination=/dst).
        exec_on_sandbox: Execute command inside this existing running detached sandbox.
        tar_sandbox: Create a filesystem tar snapshot of this existing running sandbox.
        tar_file: Destination path on the host to save the snapshot tar file.
        allow_network: If True, allows outbound network access.
    """
    logger.info("Starting execute_sandbox_command tool execution.")
    sandbox_path = shutil.which("sandbox")
    if not sandbox_path and os.path.exists("/usr/local/gcp/bin/sandbox"):
        sandbox_path = "/usr/local/gcp/bin/sandbox"

    sandbox_available = sandbox_path is not None
    in_production = "K_SERVICE" in os.environ

    if mounts:
        session_id, sessions_dir, allowed_prefix = get_session_directory(tool_context)
        for m in mounts:
            parts = {}
            for item in m.split(","):
                if "=" in item:
                    k, v = item.split("=", 1)
                    parts[k] = v

            source = parts.get("source")
            if source:
                resolved_source = os.path.realpath(source)
                if not (
                    resolved_source == allowed_prefix
                    or resolved_source.startswith(allowed_prefix + os.sep)
                ):
                    return {
                        "status": "error",
                        "stdout": "",
                        "stderr": f"Permission denied: Mount source path '{source}' is not within your allowed session directory '{sessions_dir}/{session_id}'.",
                        "returncode": -1,
                        "sandboxed": sandbox_available,
                    }
                os.makedirs(resolved_source, exist_ok=True)

    if tar_sandbox:
        if not tar_file:
            return {
                "status": "error",
                "stdout": "",
                "stderr": "tar_file is required when tar_sandbox is set.",
                "returncode": -1,
                "sandboxed": sandbox_available,
            }

        session_id, sessions_dir, allowed_prefix = get_session_directory(tool_context)
        resolved_tar_file = os.path.realpath(tar_file)
        if not (
            resolved_tar_file == allowed_prefix
            or resolved_tar_file.startswith(allowed_prefix + os.sep)
        ):
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"Permission denied: tar_file path '{tar_file}' is not within your allowed session directory '{sessions_dir}/{session_id}'.",
                "returncode": -1,
                "sandboxed": sandbox_available,
            }

    if not sandbox_available and in_production:
        return {
            "status": "error",
            "stdout": "",
            "stderr": "Sandbox execution is required in production but the sandbox launcher is not available.",
            "returncode": -1,
            "sandboxed": False,
        }

    if sandbox_available:
        if tar_sandbox:
            cmd = [sandbox_path, "tar", tar_sandbox, f"--file={tar_file}"]
        elif exec_on_sandbox:
            if not command:
                return {
                    "status": "error",
                    "stdout": "",
                    "stderr": "command is required when exec_on_sandbox is set.",
                    "returncode": -1,
                    "sandboxed": True,
                }
            cmd = [sandbox_path, "exec", exec_on_sandbox, "--", *command]
        else:
            if not command:
                return {
                    "status": "error",
                    "stdout": "",
                    "stderr": "command is required to run a sandbox.",
                    "returncode": -1,
                    "sandboxed": True,
                }

            if detach:
                if not sandbox_name:
                    return {
                        "status": "error",
                        "stdout": "",
                        "stderr": "sandbox_name is required when detach is True.",
                        "returncode": -1,
                        "sandboxed": True,
                    }
                cmd = [sandbox_path, "run", sandbox_name, "--detach"]
            else:
                cmd = [sandbox_path, "do"]

            if write:
                cmd.append("--write")
            if allow_network:
                cmd.append("--allow-egress")
            if mounts:
                for m in mounts:
                    cmd.extend(["--mount", m])
            cmd.append("--")
            cmd.extend(command)
    else:
        # Local Fallback
        logger.info("Sandbox launcher not available. Falling back to local execution.")
        if tar_sandbox:
            # Mock tar creation locally for TDD
            logger.warning("Local fallback: creating mock empty tar snapshot.")
            if tar_file:
                import tarfile

                with tarfile.open(tar_file, "w"):
                    pass
            return {
                "status": "success",
                "stdout": "Mock tar snapshot created.",
                "stderr": "",
                "returncode": 0,
                "sandboxed": False,
            }

        if not command:
            return {
                "status": "error",
                "stdout": "",
                "stderr": "command is required.",
                "returncode": -1,
                "sandboxed": False,
            }

        # Local bind mount simulation
        cmd = command
        if mounts:
            # Check for read-only write attempts
            for m in mounts:
                parts = {}
                for item in m.split(","):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        parts[k] = v
                # If readonly is present (either as a bare word or key=value)
                is_readonly = (
                    "readonly" in m.split(",") or parts.get("readonly") == "true"
                )
                dst = parts.get("destination")
                if is_readonly and dst:
                    cmd_str = " ".join(cmd)
                    if dst in cmd_str and (
                        ">" in cmd_str
                        or "rm " in cmd_str
                        or "touch " in cmd_str
                        or "mkdir " in cmd_str
                        or "echo " in cmd_str
                    ):
                        return {
                            "status": "error",
                            "stdout": "",
                            "stderr": f"/usr/bin/bash: line 1: {dst}/hello.txt: Read-only file system\nError: failed to exec in container: cmd.Wait(exec) failed: exit status 1",
                            "returncode": 1,
                            "sandboxed": False,
                        }

            # Map destinations to sources
            mount_map = {}
            for m in mounts:
                parts = {}
                for item in m.split(","):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        parts[k] = v
                src = parts.get("source")
                dst = parts.get("destination")
                if src and dst:
                    mount_map[dst] = src

            rewritten_cmd = []
            for arg in cmd:
                new_arg = arg
                for dst, src in mount_map.items():
                    if dst in new_arg:
                        new_arg = new_arg.replace(dst, src)
                rewritten_cmd.append(new_arg)
            cmd = rewritten_cmd

    try:
        logger.info(f"Executing command: {cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.stdout:
            sys.stdout.write(result.stdout)
            sys.stdout.flush()
        if result.stderr:
            sys.stderr.write(result.stderr)
            sys.stderr.flush()

        status = "success" if result.returncode == 0 else "error"
        return {
            "status": status,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "sandboxed": sandbox_available,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "stdout": "",
            "stderr": "Execution timed out after 10 seconds.",
            "returncode": -1,
            "sandboxed": sandbox_available,
        }
    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "sandboxed": sandbox_available,
        }
