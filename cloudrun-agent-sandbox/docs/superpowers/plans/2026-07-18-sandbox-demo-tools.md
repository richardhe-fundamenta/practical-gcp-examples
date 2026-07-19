# Granular Cloud Run Sandbox Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace monolithic sandbox tools with 6 granular Unix-style tools for the Gemini Enterprise sandbox demo.

**Architecture:** Split tools inside `app/tools.py` into distinct functions matching sandbox CLI commands (`do`, `run`, `exec`, `tar`, `delete`), register them in `app/agent.py`, and refactor tests for local TDD simulation.

**Tech Stack:** Python 3.13, Google Agent Development Kit (ADK), pytest.

## Global Constraints

- Preserve all existing code styling, formats, and comments.
- Do NOT change python model configuration.
- Implement robust local simulation fallbacks for development.
- Target all changes inside `/Users/rocketech/repos/practical-gcp-examples/cloudrun-agent-sandbox`.

---

## Tasks

### Task 1: Helper and Python Script Tool

Implement `get_session_directory` and the `run_python_script` tool inside `app/tools.py` with full local fallback simulation and state syncing.

**Files:**
- Modify: `app/tools.py`
- Modify: `tests/unit/test_tools.py`

**Interfaces:**
- Consumes: `ToolContext` from ADK.
- Produces:
  ```python
  def get_session_directory(tool_context: ToolContext | None = None) -> tuple[str, str, str]: ...
  def run_python_script(
      code: str,
      write: bool = False,
      allow_network: bool = False,
      sync_tar: str | None = None,
      env: dict[str, str] | None = None,
      tool_context: ToolContext | None = None
  ) -> dict: ...
  ```

- [ ] **Step 1: Write the failing tests**
  Add unit tests in `tests/unit/test_tools.py` to assert `run_python_script` behavior.
  ```python
  def test_run_python_script_local_success():
      from app.tools import run_python_script
      res = run_python_script(code="print('Hello Local')")
      assert res["status"] == "success"
      assert "Hello Local" in res["stdout"]
      assert res["sandboxed"] is False
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `uv run --env-file .env pytest tests/unit/test_tools.py::test_run_python_script_local_success`
  Expected: ImportError / AttributeError (since `run_python_script` is not defined yet).

- [ ] **Step 3: Write minimal implementation**
  Add `run_python_script` and ensure `get_session_directory` is present in `app/tools.py`.
  ```python
  def run_python_script(
      code: str,
      write: bool = False,
      allow_network: bool = False,
      sync_tar: str | None = None,
      env: dict[str, str] | None = None,
      tool_context: ToolContext | None = None
  ) -> dict:
      import logging
      import os
      import sys
      import tempfile
      import shutil
      import subprocess
      logger = logging.getLogger(__name__)
      
      temp_file_path = None
      try:
          with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
              temp_file_path = f.name
              f.write(code)
          
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
              cmd = [sandbox_path, "do"]
              if write:
                  cmd.append("--write")
              if allow_network:
                  cmd.append("--allow-egress")
              if sync_tar:
                  cmd.append(f"--sync-tar={sync_tar}")
              if env:
                  for k, v in env.items():
                      cmd.extend(["--env", f"{k}={v}"])
              cmd.extend(["--", sys.executable, temp_file_path])
          else:
              # Local fallback
              cmd = [sys.executable, temp_file_path]
          
          result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
          status = "success" if result.returncode == 0 else "error"
          return {
              "status": status,
              "stdout": result.stdout,
              "stderr": result.stderr,
              "returncode": result.returncode,
              "sandboxed": sandbox_available,
          }
      finally:
          if temp_file_path and os.path.exists(temp_file_path):
              os.remove(temp_file_path)
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `uv run --env-file .env pytest tests/unit/test_tools.py::test_run_python_script_local_success`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add app/tools.py tests/unit/test_tools.py
  git commit -m "feat: implement run_python_script tool and test"
  ```

---

### Task 2: Implement Remaining Granular Tools

Implement `run_sandbox_command`, `start_background_sandbox`, `execute_in_background_sandbox`, `snapshot_background_sandbox`, and `stop_background_sandbox` inside `app/tools.py`.

**Files:**
- Modify: `app/tools.py`
- Modify: `tests/unit/test_tools.py`

**Interfaces:**
- Consumes: `get_session_directory`
- Produces:
  ```python
  def run_sandbox_command(command: list[str], write: bool = False, allow_network: bool = False, sync_tar: str | None = None, mounts: list[str] | None = None, env: dict[str, str] | None = None, tool_context: ToolContext | None = None) -> dict: ...
  def start_background_sandbox(sandbox_name: str, command: list[str], write: bool = False, allow_network: bool = False, mounts: list[str] | None = None, env: dict[str, str] | None = None, tool_context: ToolContext | None = None) -> dict: ...
  def execute_in_background_sandbox(sandbox_name: str, command: list[str], tool_context: ToolContext | None = None) -> dict: ...
  def snapshot_background_sandbox(sandbox_name: str, tar_file_path: str, tool_context: ToolContext | None = None) -> dict: ...
  def stop_background_sandbox(sandbox_name: str, tool_context: ToolContext | None = None) -> dict: ...
  ```

- [ ] **Step 1: Write the failing tests**
  Add unit tests in `tests/unit/test_tools.py` for each of these tools under local fallback simulation.
  ```python
  def test_run_sandbox_command_local():
      from app.tools import run_sandbox_command
      res = run_sandbox_command(command=["echo", "Hello Command"])
      assert res["status"] == "success"
      assert "Hello Command" in res["stdout"]
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `uv run --env-file .env pytest tests/unit/test_tools.py::test_run_sandbox_command_local`
  Expected: AttributeError (since `run_sandbox_command` is not defined yet).

- [ ] **Step 3: Write implementation**
  Add these functions to `app/tools.py`:
  ```python
  def run_sandbox_command(
      command: list[str],
      write: bool = False,
      allow_network: bool = False,
      sync_tar: str | None = None,
      mounts: list[str] | None = None,
      env: dict[str, str] | None = None,
      tool_context: ToolContext | None = None
  ) -> dict:
      import os, shutil, subprocess
      sandbox_path = shutil.which("sandbox") or ("/usr/local/gcp/bin/sandbox" if os.path.exists("/usr/local/gcp/bin/sandbox") else None)
      sandbox_available = sandbox_path is not None
      
      if mounts:
          session_id, sessions_dir, allowed_prefix = get_session_directory(tool_context)
          for m in mounts:
              parts = {k: v for item in m.split(",") if "=" in item for k, v in [item.split("=", 1)]}
              source = parts.get("source")
              if source:
                  resolved_source = os.path.realpath(source)
                  if not (resolved_source == allowed_prefix or resolved_source.startswith(allowed_prefix + os.sep)):
                      return {"status": "error", "stdout": "", "stderr": f"Permission denied: Mount source path '{source}' is not within session directory.", "returncode": -1, "sandboxed": sandbox_available}
                  os.makedirs(resolved_source, exist_ok=True)
      
      if sandbox_available:
          cmd = [sandbox_path, "do"]
          if write: cmd.append("--write")
          if allow_network: cmd.append("--allow-egress")
          if sync_tar: cmd.append(f"--sync-tar={sync_tar}")
          if env:
              for k, v in env.items(): cmd.extend(["--env", f"{k}={v}"])
          if mounts:
              for m in mounts: cmd.extend(["--mount", m])
          cmd.append("--")
          cmd.extend(command)
      else:
          # Local mount simulation
          cmd = command
          if mounts:
              mount_map = {}
              for m in mounts:
                  parts = {k: v for item in m.split(",") if "=" in item for k, v in [item.split("=", 1)]}
                  src = parts.get("source")
                  dst = parts.get("destination")
                  if src and dst: mount_map[dst] = src
              cmd = [arg.replace(dst, src) for arg in cmd for dst, src in mount_map.items()]
      
      res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
      return {"status": "success" if res.returncode == 0 else "error", "stdout": res.stdout, "stderr": res.stderr, "returncode": res.returncode, "sandboxed": sandbox_available}

  def start_background_sandbox(
      sandbox_name: str,
      command: list[str],
      write: bool = False,
      allow_network: bool = False,
      mounts: list[str] | None = None,
      env: dict[str, str] | None = None,
      tool_context: ToolContext | None = None
  ) -> dict:
      import os, shutil, subprocess
      sandbox_path = shutil.which("sandbox") or ("/usr/local/gcp/bin/sandbox" if os.path.exists("/usr/local/gcp/bin/sandbox") else None)
      sandbox_available = sandbox_path is not None
      
      if sandbox_available:
          cmd = [sandbox_path, "run", sandbox_name, "--detach"]
          if write: cmd.append("--write")
          if allow_network: cmd.append("--allow-egress")
          if env:
              for k, v in env.items(): cmd.extend(["--env", f"{k}={v}"])
          if mounts:
              for m in mounts: cmd.extend(["--mount", m])
          cmd.append("--")
          cmd.extend(command)
          res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
          return {"status": "success" if res.returncode == 0 else "error", "stdout": res.stdout, "stderr": res.stderr, "returncode": res.returncode, "sandboxed": True}
      else:
          # Local Mock simulation
          return {"status": "success", "stdout": f"Mock background sandbox '{sandbox_name}' started locally.", "stderr": "", "returncode": 0, "sandboxed": False}

  def execute_in_background_sandbox(
      sandbox_name: str,
      command: list[str],
      tool_context: ToolContext | None = None
  ) -> dict:
      import os, shutil, subprocess
      sandbox_path = shutil.which("sandbox") or ("/usr/local/gcp/bin/sandbox" if os.path.exists("/usr/local/gcp/bin/sandbox") else None)
      sandbox_available = sandbox_path is not None
      
      if sandbox_available:
          cmd = [sandbox_path, "exec", sandbox_name, "--"] + command
          res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
          return {"status": "success" if res.returncode == 0 else "error", "stdout": res.stdout, "stderr": res.stderr, "returncode": res.returncode, "sandboxed": True}
      else:
          # Local Mock Simulation
          cmd = command
          res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
          return {"status": "success" if res.returncode == 0 else "error", "stdout": res.stdout, "stderr": res.stderr, "returncode": res.returncode, "sandboxed": False}

  def snapshot_background_sandbox(
      sandbox_name: str,
      tar_file_path: str,
      tool_context: ToolContext | None = None
  ) -> dict:
      import os, shutil, subprocess
      sandbox_path = shutil.which("sandbox") or ("/usr/local/gcp/bin/sandbox" if os.path.exists("/usr/local/gcp/bin/sandbox") else None)
      sandbox_available = sandbox_path is not None
      
      session_id, sessions_dir, allowed_prefix = get_session_directory(tool_context)
      resolved_tar = os.path.realpath(tar_file_path)
      if not (resolved_tar == allowed_prefix or resolved_tar.startswith(allowed_prefix + os.sep)):
          return {"status": "error", "stdout": "", "stderr": f"Permission denied: Tar output '{tar_file_path}' is not within session directory.", "returncode": -1, "sandboxed": sandbox_available}
      
      if sandbox_available:
          cmd = [sandbox_path, "tar", sandbox_name, f"--file={tar_file_path}"]
          res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
          return {"status": "success" if res.returncode == 0 else "error", "stdout": res.stdout, "stderr": res.stderr, "returncode": res.returncode, "sandboxed": True}
      else:
          # Local Mock Snapshot
          import tarfile
          with tarfile.open(tar_file_path, "w"): pass
          return {"status": "success", "stdout": f"Mock tar snapshot created at {tar_file_path}.", "stderr": "", "returncode": 0, "sandboxed": False}

  def stop_background_sandbox(
      sandbox_name: str,
      tool_context: ToolContext | None = None
  ) -> dict:
      import os, shutil, subprocess
      sandbox_path = shutil.which("sandbox") or ("/usr/local/gcp/bin/sandbox" if os.path.exists("/usr/local/gcp/bin/sandbox") else None)
      sandbox_available = sandbox_path is not None
      
      if sandbox_available:
          cmd = [sandbox_path, "delete", sandbox_name]
          res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
          return {"status": "success" if res.returncode == 0 else "error", "stdout": res.stdout, "stderr": res.stderr, "returncode": res.returncode, "sandboxed": True}
      else:
          return {"status": "success", "stdout": f"Mock sandbox '{sandbox_name}' deleted.", "stderr": "", "returncode": 0, "sandboxed": False}
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `uv run --env-file .env pytest tests/unit/test_tools.py::test_run_sandbox_command_local`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add app/tools.py tests/unit/test_tools.py
  git commit -m "feat: implement remaining granular tools"
  ```

---

### Task 3: Register Tools and Update Agent Configuration

Import and register the 6 new tools in `app/agent.py` and rewrite the instructions to guide the agent in selecting and using these granular tools.

**Files:**
- Modify: `app/agent.py`

**Interfaces:**
- Consumes: the 6 new tool functions.
- Produces: updated `root_agent` configuration.

- [ ] **Step 1: Modify imports and instruction configuration**
  Replace legacy imports in `app/agent.py`:
  ```python
  from app.tools import (
      run_python_script,
      run_sandbox_command,
      start_background_sandbox,
      execute_in_background_sandbox,
      snapshot_background_sandbox,
      stop_background_sandbox
  )
  ```
  Update the agent instructions to document each granular tool and its use case. Include precise instruction rules for:
  - Ephemeral Python script execution via `run_python_script`.
  - Ephemeral command execution via `run_sandbox_command`.
  - Detached background sandboxes lifecycle using `start_background_sandbox`, `execute_in_background_sandbox`, and cleanup via `stop_background_sandbox`.
  - Exporting snapshots using `snapshot_background_sandbox`.

- [ ] **Step 2: Verify imports compile**
  Run: `uv run python -c "from app.agent import root_agent"`
  Expected: Clean exit (no syntax or import errors).

- [ ] **Step 3: Commit**
  ```bash
  git add app/agent.py
  git commit -m "feat: register granular tools and update agent instructions"
  ```

---

### Task 4: Refactor Test Suites & Verify Clean Baseline

Refactor legacy test suites in `tests/unit/test_tools.py`, `tests/integration/test_agent.py`, `tests/integration/test_sandbox_agent.py`, and `tests/integration/test_server_e2e.py` to match the new tool interfaces, and verify they run successfully.

**Files:**
- Modify: `tests/unit/test_tools.py`
- Modify: `tests/integration/test_agent.py`
- Modify: `tests/integration/test_sandbox_agent.py`
- Modify: `tests/integration/test_server_e2e.py`

- [ ] **Step 1: Rewrite test suites**
  Scan and replace all references to `execute_python_code` and `execute_sandbox_command` with the appropriate granular tools in `tests/` directories. Implement robust assertions on `stdout`, `stderr`, and `returncode` for each tool.

- [ ] **Step 2: Run test suite**
  Run: `uv run --env-file .env pytest`
  Expected: 100% tests passed.

- [ ] **Step 3: Commit**
  ```bash
  git add tests/
  git commit -m "test: refactor test suites for granular tools and verify green"
  ```
