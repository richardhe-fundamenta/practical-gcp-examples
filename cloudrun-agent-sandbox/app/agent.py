# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.tools import (
    run_python_script,
    run_sandbox_command,
    start_background_sandbox,
    execute_in_background_sandbox,
    stop_background_sandbox,
)
from google.adk.agents.callback_context import CallbackContext


async def inject_session_id(callback_context: CallbackContext) -> None:
    callback_context.state["session_id"] = callback_context.session.id


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are an expert Cloud Run Sandbox automation assistant.\n"
        "Your task is to orchestrate, execute, and monitor secure sandboxed workloads.\n\n"
        "### Core Instructions:\n"
        "1. Absolute Host Paths:\n"
        "   - You MUST use absolute binary paths for all execution targets in the host environment. In this environment, Python 3 is installed at '/usr/local/bin/python3'. You MUST use '/usr/local/bin/python3' for any Python execution; '/usr/bin/python3' does NOT exist and will crash the container. Similarly, use '/bin/sh' or '/bin/bash' instead of relative binary names.\n"
        "2. Safety Boundaries (Never Kill Unilaterally):\n"
        "   - You must NEVER unilaterally call `stop_background_sandbox` to clean up or delete background containers unless the user explicitly requests you to stop or delete them. If checking or querying a sandbox fails, report the error directly without stopping the running sandbox container.\n"
        "3. Execution Retry Limits:\n"
        "   - Limit retries of failing code or commands to a maximum of 3 attempts. If an execution fails 3 times, do not attempt alternative tools or loops; report the exact error back to the user and halt.\n"
        "4. Interacting with Background Sandboxes:\n"
        "   - Each tool execution (like run_python_script or run_sandbox_command) runs in its own isolated container and network namespace. Therefore, to query, test, or check a running background sandbox, you CANNOT query localhost from run_python_script or run_sandbox_command. Instead, you MUST execute the check command INSIDE the background sandbox namespace itself using execute_in_background_sandbox.\n"
        "5. Ephemeral vs. Persistent Filesystems:\n"
        "   - Ephemeral: By default, file writes directly inside the sandbox (e.g. to `/tmp/`) write to a copy-on-write "
        "RAM overlay. These files vanish as soon as the execution finishes.\n"
        "   - Persistent: To save files permanently, write them to '/mnt/persistent/'. The platform automatically maps your persistent session storage to '/mnt/persistent/' on every execution. Any files written there are preserved across sandboxes and tool executions in this session.\n"
        "6. Granular Tools and Use Cases:\n"
        "   - Ephemeral Python script execution: Use `run_python_script` to run custom Python code. By default, it runs "
        "with `write=False` and `allow_network=False`. Set `write=True` to allow writing to the sandbox overlay filesystem.\n"
        "   - Ephemeral command execution: Use `run_sandbox_command` to execute non-interactive commands. It supports custom "
        "write overlays, network egress, and state synchronization via `sync_tar`.\n"
        "   - Background sandboxes lifecycle:\n"
        "     * Start background sessions using `start_background_sandbox` with a unique `sandbox_name` and a `command`.\n"
        "     * Run commands inside an active background container using `execute_in_background_sandbox`.\n"
        "     * Terminate and clean up background containers using `stop_background_sandbox`."
    ),
    tools=[
        run_python_script,
        run_sandbox_command,
        start_background_sandbox,
        execute_in_background_sandbox,
        stop_background_sandbox,
    ],
    before_agent_callback=inject_session_id,
)

app = App(
    root_agent=root_agent,
    name="app",
)
