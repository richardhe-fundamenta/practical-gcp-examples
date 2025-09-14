import datetime
import yaml

from google.adk.agents import Agent
from google.cloud import bigquery
from google import genai
from google.genai.types import HttpOptions
from .genai_client_decorator import GenAIClientDecorator

def _generate_sql_from_natural_language(question: str, table_info: dict) -> str:
    """Generates a SQL query from a natural language question and a table schema."""

    prompt = f"""
    Given the following BigQuery table information:
    {yaml.dump(table_info)}

    Generate a SQL query that answers the following question:
    "{question}"

    Use the table `{table_info["project_id"]}.{table_info["dataset_id"]}.{table_info["table_id"]}` in the query.

    Generate a valid SQL query.
    The query must be a valid SQL and cannot contain any non-SQL part.
    The query should not include any markdown, formatting, or code fences.
    Only return the SQL code.
    """

    print(prompt)

    response = genai_client_with_logger.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    print(response.text)

    return response.text


def _get_table_info(project_id: str, dataset_id: str, table_id: str, extra_metadata: str) -> dict:
    """Returns a dictionary with table information."""
    client = bigquery.Client()
    table = client.get_table(f"{project_id}.{dataset_id}.{table_id}")

    return {
        "project_id": project_id,
        "dataset_id": dataset_id,
        "table_id": table_id,
        "schema": [
            {
                "name": field.name,
                "type": field.field_type,
                "description": field.description,
            }
            for field in table.schema
        ],
        "labels": dict(table.labels),
        "partitioning_info": {
            "type": table.time_partitioning.type_,
            "field": table.time_partitioning.field,
        } if table.time_partitioning else None,
        "clustering_info": table.clustering_fields,
        "storage_info": {
            "num_bytes": table.num_bytes,
            "num_rows": table.num_rows,
        },
        "extra_metadata": extra_metadata,
    }


def _convert_row_to_json_serializable(row: bigquery.Row) -> dict:
    """Converts a BigQuery Row to a JSON serializable dictionary."""
    row_dict = {}
    for key, value in row.items():
        if isinstance(value, (datetime.date, datetime.datetime)):
            row_dict[key] = value.isoformat()
        else:
            row_dict[key] = value
    return row_dict


def _explore_table(
        question: str, project_id: str, dataset_id: str, table_id: str, extra_metadata: str
) -> dict:
    """Generic function to explore a BigQuery table."""
    client = bigquery.Client()

    try:
        table_info = _get_table_info(project_id, dataset_id, table_id, extra_metadata)
        sql_query = _generate_sql_from_natural_language(question, table_info)
    except Exception as e:
        return {"status": "error", "error_message": f"Failed to generate SQL: {e}"}

    if not sql_query:
        return {
            "status": "error",
            "error_message": "I could not generate a SQL query for your question.",
        }

    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)

    try:
        dry_run_job = client.query(sql_query, job_config=job_config)
    except Exception as e:
        return {"status": "error", "error_message": f"Invalid SQL query: {e}"}

    if dry_run_job.total_bytes_processed > 2048 ** 3:
        return {
            "status": "error",
            "error_message": "Query would process more than 1GB of data.",
        }

    try:
        query_job = client.query(sql_query)
        results = query_job.result()
        return {"status": "success", "report": [_convert_row_to_json_serializable(row) for row in results]}
    except Exception as e:
        return {"status": "error", "error_message": f"Failed to execute query: {e}"}


def cycle_hire(question: str) -> dict:
    """Answers questions about the cycle hire table."""
    return _explore_table(
        question,
        "bigquery-public-data",
        "london_bicycles",
        "cycle_hire",
        extra_metadata="When filtering by date or time, use the 'start_date' or 'end_date' columns"
    )


root_agent = Agent(
    name="adk_analytics_agent",
    model="gemini-2.5-flash",
    description=(
        "Agent to answer questions about Google Trends BigQuery tables."
    ),
    instruction=(
        "You are a helpful agent who can answer user questions about analytics."
    ),
    tools=[
        cycle_hire,
    ],
)

genai_client_with_logger = GenAIClientDecorator(
        agent_name=root_agent.name,
        client=genai.Client(http_options=HttpOptions(api_version="v1"))
    )
