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

import google.auth
import os
import json

from typing import List, Dict, Any
from google.cloud import bigquery
from google.adk.agents import Agent
from dotenv import load_dotenv
from app.tools_sql import dataplex_quality_analysis_query, dataplex_single_table_analysis_query, dataplex_debug_tool_query


load_dotenv()

project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'rocketech-de-pgcp-sandbox')
dataplex_project_id = os.environ.get('DATAPLEX_PROJECT_ID', 'rocketech-de-pgcp-sandbox')
dataplex_dataset_id = os.environ.get('DATAPLEX_DATASET_ID', 'dataplex_dq_demo')
dataplex_table_id = os.environ.get('DATAPLEX_TABLE_ID', 'dataplex_dq_demo_scan_results')
data_project_id = os.environ.get('DATA_PROJECT_ID', 'rocketech-de-pgcp-sandbox')
data_project_region = os.environ.get('DATA_PROJECT_REGION', 'europe-west2')

# --- Initialize BigQuery Client ---
try:
    BQ_CLIENT = bigquery.Client(project=project_id)
except Exception as e:
    print(f"Warning: Could not initialize BigQuery client. Mocking data will be used. Error: {e}")
    BQ_CLIENT = None

# --- Agent Tools (Function Declarations) ---

def dataplex_quality_analysis(limit: int = 10) -> str:
    """
    Retrieves the top N data quality issues (failures) across all tracked tables.
    The agent should list this in a tabular way for the user.
    
    Args:
        limit: The maximum number of top issues to return.

    Returns:
        A list containing a list of the top data quality issues.
    """
    sql = dataplex_quality_analysis_query(dataplex_project_id, dataplex_dataset_id, dataplex_table_id, data_project_id, data_project_region, limit)
    job = BQ_CLIENT.query(sql)
    results_iterator = job.result()
    results = [dict(row) for row in results_iterator]
    
    return results

def dataplex_single_table_analysis(table_id: str, limit: int = 50) -> str:
    """
    Performs a deep analysis on a specific BigQuery table's data quality.
    The agent should analyze the returned details and provide a deep summary 
    of what is happening with the table.
    
    Args:
        table_id: The full ID of the table (e.g., 'project.dataset.table').

    Returns:
        A comprehensive string summarizing the table's quality details.
    """
    
    sql = dataplex_single_table_analysis_query(dataplex_project_id, dataplex_dataset_id, dataplex_table_id, table_to_analyse=table_id, limit=limit)
    job = BQ_CLIENT.query(sql)
    results_iterator = job.result()
    results = [dict(row) for row in results_iterator]
    
    return results


def dataplex_debug_tool(table_id: str, rule_name: str, limit: int = 10) -> Dict[str, str]:
    """
    Retrieves table details and the BigQuery SQL query required to find all 
    records that failed the data quality rules.
    
    Args:
        table_id: The full ID of the table (e.g., 'project.dataset.table').

    Returns:
        A dictionary containing the table's name and the SQL query to run.
    """

    sql = dataplex_debug_tool_query(dataplex_project_id, dataplex_dataset_id, dataplex_table_id, table_to_analyse=table_id, rule_name=rule_name, limit=limit)
    job = BQ_CLIENT.query(sql)
    results_iterator = job.result()
    results = [dict(row) for row in results_iterator]
    
    return results

# --- Agent Definition ---

# Optimizing the instruction for ADK to ensure correct routing logic.

DATAPLEX_INSTRUCTION = f"""
You are the **Dataplex Data Quality Expert Agent**. Your sole responsibility is to route user queries to the correct BigQuery-backed Dataplex tools and format their output for the user.

Your routing logic must be strictly followed:
1.  **For requests asking for general, high-level quality issues (e.g., "show me the top 5 data quality issues," "what are the most common failures?"):** Use the `dataplex_quality_analysis` tool. After the tool returns a list of issues, present the output as a clear and professional **Markdown table**.
2.  **For requests asking about a specific table (e.g., "analyze the 'orders' table," "tell me about the 'customer_info' data quality?"):** Use the `dataplex_single_table_analysis` tool. The user must provide a table identifier (e.g., `dataset.table_name`). The tool's output is a deep analysis summary; present this summary directly to the user.
3.  **For requests asking for debugging information (e.g., "how do I get the query to see the broken data?", "what SQL do I need to run to debug failures?"):** Use the `dataplex_debug_tool`. The tool will return the SQL query based on the table_id and rule_name provided. Present the SQL query in a **code block** and tell the user they can run it in BigQuery to find the failed records. If the table_id isn't explicitly specified, try to infer it from context. 

**Crucially, you must force the correct arguments for the tools.** If a user's query suggests they want to analyze a specific table but don't provide a table name, you must ask them to provide it before calling the relevant tool.
**Make sure if there are SQL query returned in the results with regex, it's not double escaped.

After successfully retrieving data using any of the dataplex_ tools, for each issue, do a summary in a user friendly way.

"""

root_agent = Agent(
    name="dataplex_dq_agent",
    model="gemini-2.5-pro",
    instruction=DATAPLEX_INSTRUCTION,
    tools=[dataplex_quality_analysis, dataplex_single_table_analysis, dataplex_debug_tool],
)