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

import os

import google.auth
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.bigquery.mcp_schema import bq_schema_toolset
from app.bigquery.sql_tool import run_validated_sql
from app.sandbox.render_tool import render_chart
from app.skills.loader import active_skill_contract
from app.config import get_settings

# Load .env for local runs so settings (e.g. BQ_DATASET_ALLOWLIST) are available at
# import time. No-op on Cloud Run (no .env file); does not override real env vars.
load_dotenv()

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

_LOOP_INSTRUCTION = """\
You are an expert data analyst agent. Given a user question about data, follow this loop exactly:

1. DISCOVER SCHEMA: Your data lives ONLY in the allowlisted dataset(s) named in the
   DATA SOURCE block below. Use the BigQuery schema tools — list_table_ids and
   get_table_info, scoped to the configured project and those dataset(s) — to discover
   the tables, column names, types, and relationships. Do NOT use bigquery-public-data
   or any dataset not in the allowlist; the harness gate will reject them.

2. QUERY DATA: Draft a read-only BigQuery Standard SQL SELECT query that answers the
   question. Call run_validated_sql(sql=<your query>).
   - If the result has status "rejected", read the error message carefully:
     fix the SQL (correct dataset references, add missing filters or aggregations,
     stay within byte limits) and retry run_validated_sql — at most TWO retries.
     If still rejected after two retries, report the error to the user and stop.
   - If the result has status "ok", proceed with the returned rows.

3. SHAPE DATA: From the returned rows, build a JSON string that follows the EXACT
   data.json schema defined in the skill contract below (question / x / series /
   table / prior). Do not invent a different shape — your generated render code in
   step 4 must read this same structure. Keep the table small — aggregate if needed.
   This is the data_json argument.

4. GENERATE AND RENDER CHART: Generate Python code (matplotlib, Agg backend) that:
   - Reads 'data.json' from the working directory.
   - Produces a clear, well-labelled chart saved as 'output.png'.
   Then call render_chart(code=<the Python code>, data_json=<your JSON string>).

5. RETURN RESULT: If render_chart returns status "ok", return the PNG chart to the user.
   If render_chart returns status "error", report the error briefly and suggest a fix.
"""

def _data_source_block() -> str:
    """Grounding block naming the configured project + allowlisted datasets.

    Built at import time as a plain string (the A2A agent-card builder requires a
    string instruction, not a callable). GOOGLE_CLOUD_PROJECT is set above; .env is
    loaded by ADK before this module is imported, so the allowlist is available.
    Falls back gracefully if settings can't be resolved at import."""
    try:
        s = get_settings()
        datasets = ", ".join(sorted(s.dataset_allowlist)) or "(configured at deploy time)"
        return (
            "## DATA SOURCE\n"
            f"BigQuery project: `{s.project}` (data region {s.bq_data_region}).\n"
            f"Allowlisted dataset(s) you may query: {datasets}.\n"
            f"Always fully-qualify tables as `{s.project}.<dataset>.<table>`. Queries that "
            "touch any other dataset, or exceed the byte cap, are rejected by the harness."
        )
    except Exception:
        return (
            "## DATA SOURCE\n"
            "Query ONLY the allowlisted BigQuery dataset(s) configured for this deployment; "
            "fully-qualify tables as `project.dataset.table`. Other datasets are rejected."
        )


INSTRUCTION = _LOOP_INSTRUCTION + "\n\n" + _data_source_block() + "\n\n" + active_skill_contract()

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    description="A data analyst agent that queries BigQuery and renders charts.",
    instruction=INSTRUCTION,
    tools=[
        bq_schema_toolset(),
        run_validated_sql,
        render_chart,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
