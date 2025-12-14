"""Production mode tools for curated report execution."""

import asyncio
import json
import logging
from typing import Any, Optional

from google.adk.tools import FunctionTool

from .services.datastore_service import DatastoreService

logger = logging.getLogger(__name__)

# Global datastore service instance (configured by get_tools function)
_datastore_service: Optional[DatastoreService] = None


def configure(datastore_service: DatastoreService) -> None:
    """Configure production tools with datastore service instance.

    Args:
        datastore_service: DatastoreService instance to use
    """
    global _datastore_service
    _datastore_service = datastore_service
    logger.info("Production tools configured with DatastoreService")


def get_tools(datastore_service: DatastoreService) -> list:
    """Get production mode tools configured with datastore service.

    Args:
        datastore_service: DatastoreService instance

    Returns:
        List of configured FunctionTool instances
    """
    configure(datastore_service)
    return [
        FunctionTool(list_categories),
        FunctionTool(get_query_details),
        FunctionTool(execute_parameterized_query),
    ]


def list_categories() -> str:
    """List all report categories organized by business topic.

    This tool shows all available report categories in the report library,
    along with example reports in each category. Use this to discover what
    types of reports are available for different business needs.

    Returns:
        Formatted string with categories and example reports organized by topic
    """
    if _datastore_service is None:
        return json.dumps({"error": "DatastoreService not configured"})

    try:
        result = _datastore_service.list_categories_with_examples()

        # Format for better readability
        output = "Available Report Categories:\n\n"

        for cat in result["categories"]:
            output += f"**{cat['display_name']}** ({cat['id']})\n"
            output += f"  Description: {cat['description']}\n"
            output += f"  Number of reports: {cat['query_count']}\n"

            if cat["example_queries"]:
                output += "  Example reports:\n"
                for q in cat["example_queries"]:
                    output += f"    - {q['name']} (ID: {q['id']})\n"
                    output += f"      {q['description']}\n"

            output += "\n"

        return output

    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        return f"Error: {str(e)}"


def get_query_details(
    query_id: Optional[str] = None,
    query_name: Optional[str] = None,
    category: Optional[str] = None,
) -> str:
    """Get details about a specific report including natural language explanation.

    Retrieves information about a report, including what it shows (in plain English),
    what parameters it needs, and the underlying SQL. You can search by report ID,
    report name, or list all reports in a category.

    Args:
        query_id: The ID of the report (most specific)
        query_name: Name of the report to search for (partial match supported)
        category: Category to filter reports (optional)

    Returns:
        Report details with explanation and required parameters
    """
    if _datastore_service is None:
        return json.dumps({"error": "DatastoreService not configured"})

    try:
        # If query_id provided, get specific query
        if query_id:
            details = _datastore_service.get_query_details_by_id(query_id)

            output = f"**{details['name']}** (ID: {details['id']})\n\n"
            output += f"Category: {details['category']}\n\n"
            output += f"**What this report shows:**\n{details['natural_language_explanation']}\n\n"

            if details["parameters"]:
                output += "**Required Parameters:**\n"
                for p in details["parameters"]:
                    req_text = "required" if p["required"] else "optional"
                    output += f"  - **{p['name']}** ({p['type']}, {req_text})\n"
                    output += f"    {p['description']}\n"
            else:
                output += "**No parameters required**\n"

            output += f"\n**Underlying SQL:**\n```sql\n{details['sql_query']}\n```\n"

            return output

        # If query_name provided, search for matches
        elif query_name:
            matches = _datastore_service.search_queries_by_name(query_name, category)

            if not matches:
                return f"No reports found matching '{query_name}'"

            if len(matches) == 1:
                # If only one match, get full details
                return get_query_details(query_id=matches[0]["id"])

            # Multiple matches, list them
            output = f"Found {len(matches)} reports matching '{query_name}':\n\n"
            for m in matches:
                output += f"  - **{m['name']}** (ID: {m['id']})\n"
                output += f"    Category: {m['category']}\n"
                output += f"    {m['description']}\n\n"

            output += "\nUse get_query_details with a specific query_id to see full details."
            return output

        else:
            return "Please provide either query_id or query_name to get report details."

    except Exception as e:
        logger.error(f"Error getting report details: {e}")
        return f"Error: {str(e)}"


async def execute_parameterized_query(query_id: str, parameters: dict[str, Any]) -> str:
    """Execute a curated report with user-provided parameter values.

    Runs a report from the report library with the specified parameters and returns
    the results. Use get_query_details first to see what parameters are needed.

    Args:
        query_id: The ID of the report to execute
        parameters: Dictionary mapping parameter names to their values
                   Example: {"customer_id": 12345, "start_date": "2024-01-01"}

    Returns:
        Report results formatted as a table or error message
    """
    if _datastore_service is None:
        return json.dumps({"error": "DatastoreService not configured"})

    try:
        # Execute query asynchronously (already in async context)
        result = await _datastore_service.execute_query_with_parameters(query_id, parameters)

        if result["success"]:
            output = f"**Report:** {result['query_name']}\n\n"
            output += f"**Results:**\n{result['results']}\n\n"
            output += f"_Executed SQL:_\n```sql\n{result['executed_query']}\n```"
            return output
        else:
            return f"**Report execution failed:**\n{result['error']}\n\nReport: {result['query_name']}"

    except ValueError as e:
        # Parameter validation errors
        logger.warning(f"Parameter validation error: {e}")
        return f"Parameter Error: {str(e)}\n\nUse get_query_details to see required parameters."

    except Exception as e:
        logger.error(f"Error executing report: {e}")
        return f"Execution Error: {str(e)}"
