# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import logging
import os
from zoneinfo import ZoneInfo

import google.auth
from google.adk.agents import Agent
from google.adk.apps.app import App
from google.adk.tools import ToolContext
from typing import Dict, Any
from google.adk.tools import FunctionTool
from google.adk.agents.llm_agent import LlmAgent

from google.adk.tools import ToolContext
from typing import Dict, Any

_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")


AUTH_ID = "slack-oauth-auth" 

def my_auth_tool(
    tool_context: ToolContext,
    # ... other tool arguments ...
) -> Dict[str, Any]:
    """An ADK tool that requires user authentication."""
    logging.info(f"Tool Context State: {tool_context.state.to_dict()}")
    
    # 1. Retrieve the access token from the session state
    # The key used by the Agent Engine to store the token is {AUTH_ID}
    access_token = tool_context.state.get(AUTH_ID)

    if not access_token:
        # Handle the error if the token is missing or expired and the flow failed
        return {"error": "User authorization required or token retrieval failed."}
    
    # 2. Use the access token for an authenticated API call
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Use the headers to make a request to a protected resource (e.g., your internal API)
    # response = await httpx.get("https://your-protected-api.com/data", headers=headers)
    
    # 3. Return the tool result
    return {"status": "success", "message": "Authenticated call executed successfully."}

root_agent = Agent(
    name="auth_agent",
    model="gemini-2.5-flash",
    instruction="Agent to validate user authentication.",
    tools=[my_auth_tool],
)


app = App(root_agent=root_agent, name="app")
