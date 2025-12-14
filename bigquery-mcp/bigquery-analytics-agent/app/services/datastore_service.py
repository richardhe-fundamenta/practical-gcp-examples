"""Service for accessing BigQuery query templates from Cloud Datastore."""

import json
import logging
import re
from typing import Any, Optional

import google.auth
import httpx
import vertexai
from vertexai.generative_models import GenerativeModel

from ..shared.models import Category, DatastoreClient, QueryTemplate

logger = logging.getLogger(__name__)


class DatastoreService:
    """Service for accessing and executing parameterized queries from Datastore."""

    def __init__(self, project_id: str):
        """Initialize Datastore service with Gemini model for explanations.

        Args:
            project_id: GCP project ID
        """
        self.project_id = project_id
        self.datastore_client = DatastoreClient(project_id)

        # Initialize Gemini for query explanations
        vertexai.init(project=project_id, location="global")
        self.gemini_model = GenerativeModel("gemini-3-pro-preview")

        # Initialize credentials for MCP calls
        self.credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/bigquery"]
        )

        logger.info(f"DatastoreService initialized for project: {project_id}")

    def list_categories_with_examples(self) -> dict[str, Any]:
        """List all categories with example queries in each.

        Returns:
            Dictionary with categories and their example queries
        """
        categories = self.datastore_client.list_categories()

        result = {"categories": []}

        for category in categories:
            # Get sample queries for this category
            queries = self.datastore_client.list_query_templates(category=category.id)
            sample_queries = [
                {"id": q.id, "name": q.name, "description": q.description}
                for q in queries[:3]  # First 3 as examples
            ]

            result["categories"].append(
                {
                    "id": category.id,
                    "display_name": category.display_name,
                    "description": category.description,
                    "query_count": category.query_count,
                    "example_queries": sample_queries,
                }
            )

        return result

    def get_query_details_by_id(self, query_id: str) -> dict[str, Any]:
        """Get query details with natural language explanation.

        Args:
            query_id: Query template ID

        Returns:
            Dictionary with query details and explanation

        Raises:
            ValueError: If query not found
        """
        query_template = self.datastore_client.get_query_template(query_id)

        if not query_template:
            raise ValueError(f"Query not found: {query_id}")

        # Generate explanation using Gemini
        explanation = self.explain_query_with_gemini(query_template.sql_query)

        return {
            "id": query_template.id,
            "name": query_template.name,
            "description": query_template.description,
            "category": query_template.category,
            "natural_language_explanation": explanation,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                }
                for p in query_template.parameters
            ],
            "sql_query": query_template.sql_query,  # Include for transparency
        }

    def search_queries_by_name(self, query_name: str, category: Optional[str] = None) -> list[dict[str, Any]]:
        """Search for queries by name (case-insensitive).

        Args:
            query_name: Query name to search for
            category: Optional category filter

        Returns:
            List of matching queries
        """
        queries = self.datastore_client.list_query_templates(category=category)

        query_name_lower = query_name.lower()
        matches = [
            {
                "id": q.id,
                "name": q.name,
                "description": q.description,
                "category": q.category,
            }
            for q in queries
            if query_name_lower in q.name.lower()
        ]

        return matches

    def explain_query_with_gemini(self, sql_query: str) -> str:
        """Generate natural language explanation of SQL query.

        Args:
            sql_query: SQL query to explain

        Returns:
            Natural language explanation
        """
        prompt = f"""Explain what this BigQuery SQL query does in simple, natural language.

Do NOT explain the SQL syntax - instead explain WHAT data it retrieves and WHY someone would use it.
Focus on the business purpose, not technical details.

SQL Query:
{sql_query}

Explanation:"""

        try:
            response = self.gemini_model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Failed to generate explanation: {e}")
            return "Unable to generate explanation. Please refer to the SQL query."

    async def execute_query_with_parameters(
        self, query_id: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a query template with provided parameters.

        Args:
            query_id: ID of the query template to execute
            parameters: Dictionary of parameter names to values

        Returns:
            Dictionary with execution results

        Raises:
            ValueError: If query not found or missing required parameters
        """
        # Get query template
        query_template = self.datastore_client.get_query_template(query_id)
        if not query_template:
            raise ValueError(f"Query not found: {query_id}")

        # Validate parameters
        required_params = {p.name for p in query_template.parameters if p.required}
        provided_params = set(parameters.keys())

        missing = required_params - provided_params
        if missing:
            raise ValueError(
                f"Missing required parameters: {', '.join(missing)}\n"
                f"Required: {', '.join(required_params)}"
            )

        # Replace parameters in SQL
        final_query = self._replace_parameters(query_template.sql_query, parameters)

        logger.info(f"Executing query {query_id} with parameters: {parameters}")

        # Execute via BigQuery MCP
        try:
            result = await self._call_mcp_execute_sql(final_query)

            return {
                "success": True,
                "query_name": query_template.name,
                "executed_query": final_query,
                "results": result,
            }
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return {
                "success": False,
                "query_name": query_template.name,
                "executed_query": final_query,
                "error": str(e),
            }

    def _replace_parameters(self, sql_query: str, parameters: dict[str, Any]) -> str:
        """Replace @parameters in SQL query with actual values.

        Args:
            sql_query: SQL query with @parameter placeholders
            parameters: Dictionary of parameter names to values

        Returns:
            SQL query with parameters replaced
        """
        result = sql_query

        for param_name, value in parameters.items():
            # Format value based on type
            if value is None:
                formatted_value = "NULL"
            elif isinstance(value, bool):
                # Handle bool before int/float since bool is a subclass of int in Python
                formatted_value = str(value).upper()
            elif isinstance(value, (int, float)):
                # Numeric values - no quotes
                formatted_value = str(value)
            elif isinstance(value, str):
                # Try to parse numeric strings (from GUI JSON)
                try:
                    # Try integer first
                    if "." not in value:
                        int_value = int(value)
                        formatted_value = str(int_value)
                    else:
                        # Try float
                        float_value = float(value)
                        formatted_value = str(float_value)
                except (ValueError, TypeError):
                    # Not a number - treat as string and escape quotes
                    formatted_value = f"'{value.replace(chr(39), chr(39)+chr(39))}'"
            else:
                # Other types - convert to string
                formatted_value = str(value)

            # Replace @param_name with the formatted value
            result = re.sub(
                f"@{param_name}\\b",
                formatted_value,
                result,
                flags=re.IGNORECASE,
            )

        return result

    async def _call_mcp_execute_sql(self, sql_query: str) -> str:
        """Execute SQL via BigQuery MCP endpoint.

        Args:
            sql_query: SQL query to execute

        Returns:
            Formatted results

        Raises:
            Exception: If MCP call fails
        """
        # Refresh credentials
        self.credentials.refresh(google.auth.transport.requests.Request())
        oauth_token = self.credentials.token

        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "x-goog-user-project": self.project_id,
            "Content-Type": "application/json",
        }

        # Prepare JSON-RPC request
        json_rpc_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "execute_sql",
                "arguments": {
                    "query": sql_query,
                    "projectId": self.project_id,
                    "dryRun": False,  # Actually execute
                },
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://bigquery.googleapis.com/mcp",
                headers=headers,
                json=json_rpc_request,
            )

            result = response.json()

            if "error" in result:
                error_msg = result["error"].get("message", str(result["error"]))
                raise Exception(f"BigQuery MCP error: {error_msg}")

            # Extract result content
            if "result" in result and "content" in result["result"]:
                content = result["result"]["content"]
                if isinstance(content, list) and len(content) > 0:
                    return content[0].get("text", str(content))

            return str(result)
