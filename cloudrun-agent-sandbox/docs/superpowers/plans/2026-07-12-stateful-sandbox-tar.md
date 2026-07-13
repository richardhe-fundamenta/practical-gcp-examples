# Cloud Run Sandbox Stateful Tar Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement stateful execution across sandboxed code runs using the sandbox's `--import-tar` and `--export-tar` capabilities, scoped by session ID to allow users to maintain files and state across multiple conversational turns.

**Architecture:** When executing python code, the tool will check if a previous state archive (`/tmp/sandbox_state_{session_id}.tar`) exists on the host. If present, it will append `--import-tar` to restore the virtual filesystem state. It will always append `--write` and `--export-tar` to save any file creations or modifications back to the host filesystem. This enables stateful file creation and reuse.

**Tech Stack:** Python 3.12, Google ADK 2.0, Cloud Run Sandbox (--import-tar, --export-tar, --write flags).

## Global Constraints

- Python version: `>=3.11, <3.14`
- Core dependencies: `google-adk[gcp]>=2.0.0,<3.0.0`, `a2a-sdk[http-server]~=0.3.22`, `aiohttp>=3.13.4`
- GCP Project ID: `rocketech-de-pgcp-sandbox`
- GCP Region: `us-east1`
- Deployment Target: `cloud_run`
- Model Name: `gemini-flash-latest`

---

### Task 1: Update the Sandbox Tool with Stateful Import/Export

**Files:**
- Modify: `app/tools.py`
- Modify: `tests/unit/test_tools.py`

**Interfaces:**
- Consumes: `execute_python_code` from `app.tools`
- Produces: Updated `execute_python_code` supporting state preservation

- [ ] **Step 1: Write the failing tests**

Modify `tests/unit/test_tools.py` to add tests for the import/export tar behavior:

```python
@patch("shutil.which")
@patch("subprocess.run")
@patch("os.path.exists")
def test_execute_python_code_first_run_export(mock_exists: MagicMock, mock_run: MagicMock, mock_which: MagicMock) -> None:
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
    
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert "--write" in cmd
    assert any(c.startswith("--export-tar=/tmp/sandbox_state_") for c in cmd)
    assert not any(c.startswith("--import-tar=") for c in cmd)

@patch("shutil.which")
@patch("subprocess.run")
@patch("os.path.exists")
def test_execute_python_code_subsequent_run_import_export(mock_exists: MagicMock, mock_run: MagicMock, mock_which: MagicMock) -> None:
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
    
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert "--write" in cmd
    assert any(c.startswith("--import-tar=/tmp/sandbox_state_") for c in cmd)
    assert any(c.startswith("--export-tar=/tmp/sandbox_state_") for c in cmd)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_tools.py -v`
Expected: FAIL (assertion on `--write` or `--export-tar` missing in command arguments)

- [ ] **Step 3: Update tool implementation**

Modify `app/tools.py` to add state import/export functionality:

```python
import os
import shutil
import sys
import subprocess
import tempfile
from google.adk.tools import ToolContext

def execute_python_code(
    code: str,
    allow_network: bool = False,
    tool_context: ToolContext | None = None
) -> dict:
    """Executes arbitrary Python code in a secure Cloud Run sandbox environment.

    Args:
        code: The Python code string to execute.
        allow_network: Set to True if the code requires outbound network access (e.g., fetching a URL or API). Defaults to False.
        tool_context: Context of the tool call, used to retrieve session state and ID.

    Returns:
        A dictionary containing the execution status ('success' or 'error'),
        stdout, stderr, exit code, and whether it was run inside the sandbox.
    """
    sandbox_available = False
    temp_file_path = None
    
    try:
        sandbox_available = shutil.which("sandbox") is not None
        in_production = "K_SERVICE" in os.environ
        
        if not sandbox_available and in_production:
            return {
                "status": "error",
                "stdout": "",
                "stderr": "Sandbox execution is required in production but the sandbox launcher is not available.",
                "returncode": -1,
                "sandboxed": False
            }
            
        # Create a temporary file to write the python code
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            temp_file_path = f.name
            f.write(code)

        if sandbox_available:
            cmd = ["sandbox", "do", "--write"]
            
            # Scoping state by session ID
            session_id = "default_session"
            if tool_context and tool_context.state:
                # Read session ID from tool context if available
                # Note: tool_context.state can store session markers
                session_id = tool_context.state.get("session_id", "default_session")
            
            state_tar_path = f"/tmp/sandbox_state_{session_id}.tar"
            
            if os.path.exists(state_tar_path):
                cmd.append(f"--import-tar={state_tar_path}")
            cmd.append(f"--export-tar={state_tar_path}")
            
            if allow_network:
                cmd.append("--allow-egress")
            cmd.extend(["--", "python3", temp_file_path])
        else:
            # Local fallback for development and testing
            cmd = [sys.executable, temp_file_path]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        status = "success" if result.returncode == 0 else "error"
        return {
            "status": status,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "sandboxed": sandbox_available
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "stdout": "",
            "stderr": "Execution timed out after 10 seconds. Check for infinite loops or blockages.",
            "returncode": -1,
            "sandboxed": sandbox_available
        }
    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "sandboxed": sandbox_available
        }
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/tools.py tests/unit/test_tools.py
git commit -m "feat: implement stateful import/export tar archives in sandbox tool"
```

---

### Task 2: Implement Stateful Agent Callbacks and Integration Tests

**Files:**
- Modify: `app/agent.py`
- Modify: `tests/integration/test_sandbox_agent.py`
- Modify: `tests/eval/datasets/basic-dataset.json`

**Interfaces:**
- Consumes: `execute_python_code` from `app.tools`
- Produces: Agent propagating session ID to the tool context

- [ ] **Step 1: Write the failing integration test**

Create/update `tests/integration/test_sandbox_agent.py` to ensure the session ID is set up in `tool_context.state`:

```python
from google.adk.tools import ToolContext
from app.agent import root_agent
from app.tools import execute_python_code

# Simple mock context
class MockToolContext:
    def __init__(self, session_id):
        self.state = {"session_id": session_id}

def test_execute_python_code_propagates_session_id():
    ctx = MockToolContext("test_session_123")
    # This shouldn't crash and should correctly read session_id
    res = execute_python_code("print('hello')", tool_context=ctx)
    assert res["status"] == "success"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_sandbox_agent.py -v`
Expected: FAIL

- [ ] **Step 3: Update Agent system callback or configuration**

Modify `app/agent.py` to inject the current session ID into the state before running tools. We can do this using a `before_agent_callback`:

```python
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from app.tools import execute_python_code

# ... existing code ...

async def inject_session_id(callback_context: CallbackContext) -> None:
    # Inject session ID so it's readable in the ToolContext.state during execution
    callback_context.state["session_id"] = callback_context.session.id

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a helpful AI assistant designed to provide accurate and useful information. "
        "You have access to a secure Cloud Run sandbox environment where you can execute Python code "
        "using the `execute_python_code` tool. Use this tool whenever the user asks for complex math, "
        "algorithms, data processing, formatting, list sorting, or code verification. "
        "By default, the sandbox does not have network access. If the user request specifically requires "
        "making network requests (e.g. hitting an API or downloading a webpage), set the `allow_network` "
        "parameter to True. Otherwise, leave it as False."
    ),
    tools=[get_weather, get_current_time, execute_python_code],
    before_agent_callback=inject_session_id,
)

app = App(
    root_agent=root_agent,
    name="app",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_sandbox_agent.py -v`
Expected: PASS

Run evaluation to verify no regressions:
Run: `uv run --env-file .env agents-cli eval run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/agent.py tests/integration/test_sandbox_agent.py
git commit -m "feat: inject session ID in before_agent_callback to scope sandbox state"
```
