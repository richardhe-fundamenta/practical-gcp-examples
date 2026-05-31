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
   - IMPORTANT: column VALUES are case-sensitive and are NOT given by get_table_info
     (which returns only column names/types). Before filtering a categorical column
     (e.g. status, region, plan_tier), if you are unsure of its exact values, FIRST run
     `SELECT DISTINCT <column> FROM ... LIMIT 50` to learn them, then filter accordingly.
   - status "rejected": read the error, fix the SQL (dataset refs, filters, byte limits)
     and retry run_validated_sql — at most TWO retries; then report and stop.
   - status "ok" but EMPTY "rows": do NOT render and do NOT invent data. Empty almost
     always means a filter value is wrong (often the wrong case, e.g. 'Completed' vs
     'completed') or a join dropped rows. Run `SELECT DISTINCT` on your filtered column(s)
     to find the real values, then retry — at most TWO retries. If still empty, tell the
     user no matching data was found and stop.
   - status "ok" with rows: continue. These rows are now the ONLY data that will be charted.

3. DATA IS HANDLED FOR YOU — DO NOT BUILD OR PASS IT. The harness automatically gives the
   renderer the rows from your most recent successful run_validated_sql call, as
   data.json = {"rows": [ ...those exact rows... ]}. You cannot change these values; this
   guarantees the chart reflects only real queried data. (So make sure your final
   successful query returns exactly the rows you want charted — aggregate in SQL.)

4. GENERATE AND RENDER CHART: Generate Python code (matplotlib, Agg backend) that:
   - Reads 'data.json' (a dict with key "rows", a list of record dicts) from the working
     directory, and shapes/aggregates those rows as needed for the chart.
   - Produces ONE clear, well-labelled chart (headline finding as the title) saved as
     'output.png'. Never hardcode data values in the code.
   Then call render_chart(code=<the Python code>). render_chart takes ONLY the code.

5. RETURN RESULT: If render_chart returns status "ok", return the PNG chart to the user
   with a short headline finding. If render_chart returns status "error", report the error
   briefly and suggest a fix.
   GROUNDING RULE for your text answer: every number you state in words (totals, deltas,
   percentages, "leads by X%") MUST be present in, or a correct simple aggregation of, the
   exact rows returned by run_validated_sql. Do NOT compute elaborate statistics in your
   head. If you want to state a precise total or percentage, get it by running another
   validated SQL query that computes it. Otherwise keep the headline qualitative (e.g.
   "NA leads every month") and let the chart and its table show the exact figures.
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
        model="gemini-3.1-pro-preview",
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
