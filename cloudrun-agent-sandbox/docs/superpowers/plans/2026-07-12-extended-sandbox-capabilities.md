# Extended Sandbox Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Cloud Run Sandbox capabilities of the agent to support detached background sandboxes, filesystem snapshotting, bind mounts, and standard stream logging to Cloud Logging.

**Architecture:** We will introduce a new general-purpose `execute_sandbox_command` tool alongside `execute_python_code` in `app/tools.py`. The tool will support custom sandbox arguments (`--detach`, `--mount`, `exec`, and `tar`) and will fall back gracefully to local execution during development. To ensure standard streams are captured in Cloud Logging while keeping execution results visible to the LLM agent, both tools will capture subprocess outputs and immediately write/flush them to `sys.stdout` and `sys.stderr`.

**Tech Stack:** Python 3.12, Google ADK 2.x, pytest, Cloud Run Sandbox CLI.

## Global Constraints
- Python version: >=3.11, <3.14
- Core dependencies: google-adk[gcp]>=2.0.0,<3.0.0, a2a-sdk[http-server]~=0.3.22, aiohttp>=3.13.4
- GCP Project ID: rocketech-de-pgcp-sandbox
- GCP Region: us-east1
- Deployment Target: cloud_run
- Model Name: gemini-flash-latest

---

## File Structure

- [app/tools.py](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/app/tools.py): 
  - Update `execute_python_code` to route captured standard output/error to `sys.stdout`/`sys.stderr`.
  - Add `execute_sandbox_command` tool to execute arbitrary commands, handle mounts, detached sandboxes, snapshotting, and logs.
- [app/agent.py](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/app/agent.py): Register `execute_sandbox_command` on the agent and update instruction context.
- [tests/unit/test_tools.py](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/tests/unit/test_tools.py): Add unit tests validating standard stream routing, detached running, mounts, snapshots, and fallbacks.
- [tests/integration/test_sandbox_agent.py](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/tests/integration/test_sandbox_agent.py): Validate agent tool registration for the new tool.
- [README.md](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/README.md): Document new sandbox examples and configuration options.

---

### Task 1: Stream Routing in execute_python_code

**Files:**
- Modify: [app/tools.py](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/app/tools.py)
- Test: [tests/unit/test_tools.py](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/tests/unit/test_tools.py)

**Interfaces:**
- Consumes: None
- Produces: Updated stream-routing logic inside `execute_python_code`.

- [ ] **Step 1: Write the failing unit test**
  Add a unit test in `tests/unit/test_tools.py` to verify that executing code routes standard output and error to `sys.stdout` and `sys.stderr`. We will mock/spy on `sys.stdout.write` and `sys.stderr.write`.

  ```python
  from unittest.mock import patch
  import sys
  from app.tools import execute_python_code

  def test_execute_python_code_routes_streams():
      code = "import sys; print('hello-stdout'); print('hello-stderr', file=sys.stderr)"
      with patch.object(sys.stdout, 'write') as mock_stdout_write, \
           patch.object(sys.stderr, 'write') as mock_stderr_write:
          result = execute_python_code(code)
          assert result["status"] == "success"
          assert "hello-stdout" in result["stdout"]
          assert "hello-stderr" in result["stderr"]
          # Verify sys.stdout and sys.stderr received the output
          mock_stdout_write.assert_any_call("hello-stdout\n")
          mock_stderr_write.assert_any_call("hello-stderr\n")
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `uv run pytest tests/unit/test_tools.py -k test_execute_python_code_routes_streams -v`
  Expected: FAIL (assertion fails since streams are not routed to `sys.stdout`/`sys.stderr` yet).

- [ ] **Step 3: Implement stream routing in execute_python_code**
  Update `execute_python_code` in `app/tools.py` to write and flush to `sys.stdout` and `sys.stderr` immediately after `subprocess.run` completes.

  ```python
  # In app/tools.py:
  # After subprocess.run completes:
  if result.stdout:
      sys.stdout.write(result.stdout)
      sys.stdout.flush()
  if result.stderr:
      sys.stderr.write(result.stderr)
      sys.stderr.flush()
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `uv run pytest tests/unit/test_tools.py -k test_execute_python_code_routes_streams -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add app/tools.py tests/unit/test_tools.py
  git commit -m "feat: route sandbox standard output/error to host stdout/stderr"
  ```

---

### Task 2: Implement execute_sandbox_command

**Files:**
- Modify: [app/tools.py](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/app/tools.py)
- Test: [tests/unit/test_tools.py](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/tests/unit/test_tools.py)

**Interfaces:**
- Consumes: Sandbox path detection logic.
- Produces: `execute_sandbox_command` tool.

- [ ] **Step 1: Write failing unit tests**
  Add unit tests in `tests/unit/test_tools.py` verifying that:
  - Command formatting constructs the sandbox command correctly (handling `--detach`, `--write`, `--mount`, `sandbox exec`, and `sandbox tar`).
  - Graceful local fallback runs the command directly.

  ```python
  from unittest.mock import patch, MagicMock
  import shutil
  from app.tools import execute_sandbox_command

  def test_execute_sandbox_command_formats_run():
      with patch("shutil.which", return_value="/usr/local/gcp/bin/sandbox"), \
           patch("subprocess.run") as mock_run:
          mock_run.return_value = MagicMock(returncode=0, stdout="out", stderr="")
          
          # Test running detached
          execute_sandbox_command(
              command=["/bin/sleep", "10m"],
              detach=True,
              sandbox_name="my-bg-sandbox",
              write=True,
              mounts=["type=bind,source=/tmp/vol,destination=/mnt/vol"]
          )
          
          expected_cmd = [
              "/usr/local/gcp/bin/sandbox", "run", "my-bg-sandbox",
              "--detach", "--write",
              "--mount", "type=bind,source=/tmp/vol,destination=/mnt/vol",
              "--", "/bin/sleep", "10m"
          ]
          mock_run.assert_called_with(expected_cmd, capture_output=True, text=True, timeout=10)

  def test_execute_sandbox_command_formats_exec():
      with patch("shutil.which", return_value="/usr/local/gcp/bin/sandbox"), \
           patch("subprocess.run") as mock_run:
          mock_run.return_value = MagicMock(returncode=0, stdout="out", stderr="")
          
          # Test executing inside existing named sandbox
          execute_sandbox_command(
              command=["/bin/echo", "hello"],
              exec_on_sandbox="my-bg-sandbox"
          )
          
          expected_cmd = [
              "/usr/local/gcp/bin/sandbox", "exec", "my-bg-sandbox",
              "--", "/bin/echo", "hello"
          ]
          mock_run.assert_called_with(expected_cmd, capture_output=True, text=True, timeout=10)

  def test_execute_sandbox_command_formats_tar():
      with patch("shutil.which", return_value="/usr/local/gcp/bin/sandbox"), \
           patch("subprocess.run") as mock_run:
          mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
          
          # Test creating a tar snapshot
          execute_sandbox_command(
              tar_sandbox="my-bg-sandbox",
              tar_file="/tmp/snapshot.tar"
          )
          
          expected_cmd = [
              "/usr/local/gcp/bin/sandbox", "tar", "my-bg-sandbox",
              "--file=/tmp/snapshot.tar"
          ]
          mock_run.assert_called_with(expected_cmd, capture_output=True, text=True, timeout=10)
  ```

- [ ] **Step 2: Run tests to verify they fail**
  Run: `uv run pytest tests/unit/test_tools.py -k "execute_sandbox_command" -v`
  Expected: FAIL (ImportError or NameError since the tool doesn't exist).

- [ ] **Step 3: Implement execute_sandbox_command**
  Define `execute_sandbox_command` in `app/tools.py` supporting all flags, absolute path sandbox fallback, stream logging, and TDD-friendly local execution fallback.

  ```python
  # In app/tools.py:
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
              if not tar_file:
                  return {"status": "error", "stdout": "", "stderr": "tar_file is required when tar_sandbox is set.", "returncode": -1, "sandboxed": True}
              cmd = [sandbox_path, "tar", tar_sandbox, f"--file={tar_file}"]
          elif exec_on_sandbox:
              if not command:
                  return {"status": "error", "stdout": "", "stderr": "command is required when exec_on_sandbox is set.", "returncode": -1, "sandboxed": True}
              cmd = [sandbox_path, "exec", exec_on_sandbox, "--"] + command
          else:
              if not command:
                  return {"status": "error", "stdout": "", "stderr": "command is required to run a sandbox.", "returncode": -1, "sandboxed": True}
              
              if detach:
                  if not sandbox_name:
                      return {"status": "error", "stdout": "", "stderr": "sandbox_name is required when detach is True.", "returncode": -1, "sandboxed": True}
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
                  with open(tar_file, "w") as f:
                      f.write("")
              return {"status": "success", "stdout": "Mock tar snapshot created.", "stderr": "", "returncode": 0, "sandboxed": False}
          
          if not command:
              return {"status": "error", "stdout": "", "stderr": "command is required.", "returncode": -1, "sandboxed": False}
          cmd = command

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
      except subprocess.TimeoutExpired as e:
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
  ```

- [ ] **Step 4: Run tests to verify they pass**
  Run: `uv run pytest tests/unit/test_tools.py -k "execute_sandbox_command" -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add app/tools.py tests/unit/test_tools.py
  git commit -m "feat: implement execute_sandbox_command tool for background sandboxes, mounts, and snapshots"
  ```

---

### Task 3: Register Tool and Update Integration Tests

**Files:**
- Modify: [app/agent.py](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/app/agent.py)
- Modify: [tests/integration/test_sandbox_agent.py](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/tests/integration/test_sandbox_agent.py)

**Interfaces:**
- Consumes: `execute_sandbox_command` from `app/tools.py`.
- Produces: Registered agent capability.

- [ ] **Step 1: Write failing integration test**
  Add a test to `tests/integration/test_sandbox_agent.py` asserting that `execute_sandbox_command` is imported and registered in the `root_agent`'s tools list.

  ```python
  # In tests/integration/test_sandbox_agent.py:
  def test_agent_registers_sandbox_command_tool():
      from app.agent import root_agent
      tool_names = [tool.__name__ for tool in root_agent.tools]
      assert "execute_sandbox_command" in tool_names
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `uv run pytest tests/integration/test_sandbox_agent.py -k test_agent_registers_sandbox_command_tool -v`
  Expected: FAIL

- [ ] **Step 3: Register the tool in app/agent.py**
  Import and add `execute_sandbox_command` to the `root_agent` tools list and update agent instructions.

  ```python
  # In app/agent.py:
  from app.tools import execute_python_code, execute_sandbox_command

  # Update root_agent:
  root_agent = Agent(
      name="root_agent",
      model=Gemini(
          model="gemini-flash-latest",
          retry_options=types.HttpRetryOptions(attempts=3),
      ),
      instruction=(
          "You are a helpful AI assistant designed to provide accurate and useful information. "
          "You have access to a secure Cloud Run sandbox environment where you can execute Python code "
          "using the `execute_python_code` tool, or run arbitrary sandbox command operations (like background tasks, "
          "snapshots, and mounts) using the `execute_sandbox_command` tool."
      ),
      tools=[execute_python_code, execute_sandbox_command],
      before_agent_callback=inject_session_id,
  )
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `uv run pytest tests/integration/test_sandbox_agent.py -k test_agent_registers_sandbox_command_tool -v`
  Expected: PASS

- [ ] **Step 5: Run the entire test suite**
  Run: `uv run pytest`
  Expected: All 18 tests PASS.

- [ ] **Step 6: Commit**
  ```bash
  git add app/agent.py tests/integration/test_sandbox_agent.py
  git commit -m "feat: register execute_sandbox_command tool on root_agent"
  ```

---

### Task 4: Update README.md with Detailed Examples

**Files:**
- Modify: [README.md](file:///Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox/README.md)

**Interfaces:**
- Consumes: None
- Produces: Updated documentation.

- [ ] **Step 1: Append new sandbox capability sections to README.md**
  Append documentation explaining:
  - Detached background execution (`--detach` and `exec`).
  - Snapshotting with `sandbox tar`.
  - Default read-only access and sharing data using bind mounts.
  - Standard stream log routing in Cloud Logging.

  Include precise markdown examples matching the requested command usages.

- [ ] **Step 2: Commit**
  ```bash
  git add README.md
  git commit -m "docs: document background sandbox, snapshotting, and mount examples in README"
  ```

---

## Plan Verification

To verify that the entire implementation complies with all constraints, run:
1. `uv run pytest` - Verify all unit and integration tests pass cleanly.
2. `agents-cli lint` - Check codebase compliance.
3. Rerun a remote deployment check via `./deploy.sh` (if approved) to confirm no compilation issues.
