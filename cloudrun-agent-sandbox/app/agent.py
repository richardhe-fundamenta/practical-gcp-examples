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

from app.tools import execute_python_code, execute_sandbox_command
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
        "Your task is to orchestrate, execute, and monitor secure sandboxed workloads. You have access to "
        "the `execute_python_code` tool (for running scripts) and `execute_sandbox_command` (for advanced controls "
        "such as background sandboxes, exec, and bind mounts).\n\n"
        "### Core Instructions:\n"
        "1. Dynamic Session Scoping: You must NEVER hardcode the string 'default_session'. Instead, read the active "
        "session ID dynamically from `state.session_id` (or fall back to 'default_session' if not present). Construct "
        "your host paths using the format `/sessions/{session_id}/` (in production) or `/tmp/{session_id}/` (during local testing).\n"
        "2. Ephemeral vs. Persistent Filesystems:\n"
        "   - Ephemeral: By default, file writes directly inside the sandbox (e.g. to `/tmp/`) write to a copy-on-write "
        "RAM overlay. These files vanish as soon as the execution finishes.\n"
        "   - Persistent: To save files permanently to the GCS FUSE bucket, you MUST configure a bind mount. Use "
        "`mounts=['type=bind,source=/sessions/{session_id}/<subpath>,destination=/mnt/<mount-dir>']` to map host folders "
        "into the sandbox.\n"
        "3. Background Sandboxes:\n"
        "   - Start background tasks by passing `detach=True`, `sandbox_name='<name>'`, and `write=True` to `execute_sandbox_command`.\n"
        "   - Run checks or interact with active background containers by passing `exec_on_sandbox='<name>'`.\n"
        "4. Snapshotting State:\n"
        "   - Capture the sandbox overlay modifications at any time using `tar_sandbox='<name>'` and `tar_file='/sessions/{session_id}/<name>.tar'`."
    ),
    tools=[execute_python_code, execute_sandbox_command],
    before_agent_callback=inject_session_id,
)

app = App(
    root_agent=root_agent,
    name="app",
)
