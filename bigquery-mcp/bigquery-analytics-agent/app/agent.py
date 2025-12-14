# ruff: noqa
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
import os
import google.auth

from zoneinfo import ZoneInfo
from google.adk.agents import Agent, LlmAgent
from google.adk.apps.app import App
from app import tools

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
bigquery_toolset = tools.get_bigquery_mcp_toolset()

root_agent = Agent(
    name="root_agent",
    model="gemini-3-pro-preview",
    instruction=f"""
                    Help the user answer questions on dataset, tables in this project "{project_id}".
                    For any request need to call the execute_sql tool, you must not automatically generate the SQL, but instead using the SQL passed from the user.
                """,
    tools=[bigquery_toolset]
)


app = App(root_agent=root_agent, name="app")