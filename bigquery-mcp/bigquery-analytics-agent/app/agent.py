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

import os
import logging
from dotenv import load_dotenv

from google.adk.agents import Agent
from google.adk.apps.app import App
from app import config
from . import explore_tools
from . import production_tools
from .services.datastore_service import DatastoreService

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Initialize project and environment
project_id = os.environ.get("PROJECT_ID")
if not project_id:
    raise ValueError("PROJECT_ID environment variable is not set. Please check your .env file.")

os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# Initialize services
datastore_service = DatastoreService(project_id)
bigquery_toolset = explore_tools.get_bigquery_mcp_toolset()

logger.info(f"Agent initialized for project: {project_id}")


# Create unified agent with both explore and production tools
unified_instruction = f"""
You are a BigQuery analytics assistant with TWO MODES of operation.

You start in EXPLORE MODE by default. The user can ask you to switch modes at any time.

## EXPLORE MODE (DEFAULT)
When in explore mode or when the user asks for ad-hoc queries:
- Use the BigQuery MCP toolset to generate and execute SQL automatically
- Answer analytical questions by writing and running SQL
- Explore datasets, tables, and schemas freely
- Be proactive in generating queries

## PRODUCTION MODE
When the user says "activate production mode", "use production mode", "switch to production", or similar:
- Acknowledge the mode switch
- Use ONLY the production tools: list_categories, get_query_details, execute_parameterized_query
- Do NOT use BigQuery MCP tools for SQL generation
- Access a library of curated reports organized by business topic
- Each report is a pre-approved, parameterized query template
- Help users discover and run the right reports for their needs

## Mode Switching
- Detect when users want to switch modes from their language
- Confirm the mode switch explicitly
- Explain what's available in the current mode

Current project: {project_id}
"""

# Get both toolsets
production_toolset = production_tools.get_tools(datastore_service)

# Create agent with all tools
root_agent = Agent(
    name="bigquery_analytics_agent",
    model=config.GEMINI_MODEL,
    instruction=unified_instruction,
    tools=[bigquery_toolset] + production_toolset
)

app = App(root_agent=root_agent, name="app")
