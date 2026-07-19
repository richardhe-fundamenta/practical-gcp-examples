# Spec: Granular Cloud Run Sandbox Tools for Technical Showcase

## 1. Overview & Context

This document specifies the design for replacing the monolithic `execute_sandbox_command` and `execute_python_code` tools in the **Cloud Run Agent Sandbox** with a set of granular, Unix-style primitives. 

The goal of this refactoring is to support a high-fidelity technical showcase demo built on the **Gemini Enterprise App**. By exposing focused, parameter-rich tools that map directly to the underlying `sandbox` CLI commands (`do`, `run`, `exec`, `tar`, `delete`), the agent's reasoning traces and tool calls will be highly readable, self-documenting, and educational for developers watching the demo.

---

## 2. Granular Tool Definitions

We will define 6 new tools to completely replace the existing ones. Each tool includes strict validations, session scoping, and automatic local fallback behaviors for local testing (TDD).

### 2.1. `run_python_script`
Runs a block of Python code inside a fresh, ephemeral sandbox.

* **Signature**:
  ```python
  def run_python_script(
      code: str,
      write: bool = False,
      allow_network: bool = False,
      sync_tar: str | None = None,
      env: dict[str, str] | None = None,
      tool_context: ToolContext | None = None
  ) -> dict:
  ```
* **Behavior**:
  * Writes `code` to a temporary script file on the host.
  * Constructs the CLI command:
    `sandbox do [--write] [--allow-egress] [--sync-tar=sync_tar] [--env KEY=VAL ...] -- python3 <temp_file>`
  * Returns stdout, stderr, exit code, and whether execution was sandboxed.

### 2.2. `run_sandbox_command`
Runs an arbitrary command in a fresh, ephemeral sandbox (`sandbox do`).

* **Signature**:
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
  ```
* **Behavior**:
  * Validates that any mount sources reside within the session's directory.
  * Constructs:
    `sandbox do [--write] [--allow-egress] [--sync-tar=sync_tar] [--mount type=bind,source=SRC,destination=DST ...] [--env KEY=VAL ...] -- <command>`

### 2.3. `start_background_sandbox`
Starts a detached sandbox container in the background (`sandbox run --detach`).

* **Signature**:
  ```python
  def start_background_sandbox(
      sandbox_name: str,
      command: list[str],
      write: bool = False,
      allow_network: bool = False,
      mounts: list[str] | None = None,
      env: dict[str, str] | None = None,
      tool_context: ToolContext | None = None
  ) -> dict:
  ```
* **Behavior**:
  * Validates mounts and creates directory paths.
  * Constructs:
    `sandbox run <sandbox_name> --detach [--write] [--allow-egress] [--mount ...] [--env ...] -- <command>`

### 2.4. `execute_in_background_sandbox`
Executes an interactive command inside a running background sandbox (`sandbox exec`).

* **Signature**:
  ```python
  def execute_in_background_sandbox(
      sandbox_name: str,
      command: list[str],
      tool_context: ToolContext | None = None
  ) -> dict:
  ```
* **Behavior**:
  * Constructs:
    `sandbox exec <sandbox_name> -- <command>`

### 2.5. `snapshot_background_sandbox`
Captures the modified filesystem overlay of a running background sandbox to a tar file (`sandbox tar`).

* **Signature**:
  ```python
  def snapshot_background_sandbox(
      sandbox_name: str,
      tar_file_path: str,
      tool_context: ToolContext | None = None
  ) -> dict:
  ```
* **Behavior**:
  * Validates that `tar_file_path` resides within the session's allowed directory.
  * Constructs:
    `sandbox tar <sandbox_name> --file=<tar_file_path>`

### 2.6. `stop_background_sandbox`
Deletes/terminates a running background sandbox container (`sandbox delete`).

* **Signature**:
  ```python
  def stop_background_sandbox(
      sandbox_name: str,
      tool_context: ToolContext | None = None
  ) -> dict:
  ```
* **Behavior**:
  * Constructs:
    `sandbox delete <sandbox_name>`

---

## 3. Video Demo Scenarios

We have mapped the tools to 5 realistic user-facing scenarios. These scenarios will run sequentially in the Gemini Enterprise App chat to showcase sandbox capabilities.

### Scenario 1: Code Isolation & Internet Egress Blocking
* **Goal**: Show that the sandbox blocks internet access by default, but allows isolated local computation.
* **Part A: Local Success**
  * **User**: *"Compute the first 10 Fibonacci numbers in the sandbox."*
  * **Agent**: Calls `run_python_script` with `allow_network=False`. Script succeeds.
* **Part B: Blocked Egress**
  * **User**: *"Download the homepage of google.com and print its length."*
  * **Agent**: Calls `run_python_script` with `allow_network=False`. Connection is blocked. Agent reports the connection failure as a security boundary success.

### Scenario 2: Session State Persistence (Sync Tar)
* **Goal**: Show state persistence across separate sandbox invocations using tar sync.
* **User Prompt 1**: *"Generate a mock dataset of 5 customer names and save it to `/tmp/customers.csv` inside the sandbox."*
* **Agent**: Calls `run_python_script` with `write=True` and `sync_tar="/sessions/{session_id}/state.tar"`.
* **User Prompt 2**: *"Read the customer CSV we just created and print them in uppercase."*
* **Agent**: Calls `run_python_script` with `write=True` and the same `sync_tar` path. It successfully reads the file, demonstrating persistence.

### Scenario 3: Persistent Background Services (Run & Exec)
* **Goal**: Show how to launch background daemons and execute queries inside them.
* **User**: *"Launch a background python web server inside the sandbox named `web-server` on port 8000, and then query it to verify it's active."*
* **Agent**:
  1. Calls `start_background_sandbox` with `sandbox_name="web-server"` and command `["python3", "-m", "http.server", "8000"]`.
  2. Calls `execute_in_background_sandbox` on `web-server` running `["curl", "http://127.0.0.1:8000"]`.
  3. Returns the index page response.

### Scenario 4: Filesystem Snapshots (Tar Capture)
* **Goal**: Capture and backup container changes, then clean up the sandbox.
* **User**: *"Export a snapshot of our `web-server` container's files so I can download it as a backup."*
* **Agent**:
  1. Calls `snapshot_background_sandbox` targeting `web-server` saving to `/sessions/{session_id}/web_server_backup.tar`.
  2. Calls `stop_background_sandbox` to delete the `web-server` sandbox container.

### Scenario 5: Shared Storage (Bind Mounts)
* **Goal**: Show file sharing between the host (e.g. GCS FUSE bucket) and the sandbox container.
* **User**: *"Write a file to my session folder `/sessions/{session_id}/shared-data` from inside the sandbox using a bind mount."*
* **Agent**:
  1. Calls `run_sandbox_command` with mount `type=bind,source=/sessions/{session_id}/shared-data,destination=/mnt/shared` executing `["bash", "-c", "echo 'Written from Sandbox' > /mnt/shared/proof.txt"]`.
  2. Reads the file `/sessions/{session_id}/shared-data/proof.txt` directly on the host to verify the shared write.

---

## 4. Local Simulation Fallback (TDD Support)

To allow developers to run tests and verify agent behavior locally (where the `sandbox` utility is not installed), the tools will simulate sandbox behaviors:
* **Egress Simulation**: If running locally and `allow_network=False`, Python script network requests will be intercepted/blocked or a warning will be logged.
* **Mount Simulation**: Rewrites directory paths mapping the destination `/mnt/shared` back to the host source path for local execution.
* **Background & Exec Simulation**: Simulates named background processes via standard Python subprocess/daemon tracking.
* **Snapshot Simulation**: Creates an empty/mock tar file locally when snapshotting is requested.

---

## 5. Implementation Steps

1. **Refactor `app/tools.py`**:
   * Implement the helper `get_session_directory`.
   * Add the 6 new granular tools with full logging, security checks, and local fallback paths.
   * Remove the legacy `execute_python_code` and `execute_sandbox_command`.
2. **Update `app/agent.py`**:
   * Import the 6 new tools and register them under the agent's `tools` array.
   * Update the agent instructions to detail when and how to use each tool.
3. **Rewrite Tests**:
   * Refactor `tests/unit/test_tools.py` to test each of the 6 tools individually under local fallback mode.
   * Refactor integration tests `tests/integration/test_sandbox_agent.py` and `tests/integration/test_agent.py`.
   * Run the test suite to verify 100% test success.
