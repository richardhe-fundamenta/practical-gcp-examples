"""MCP service for BigQuery query generation, validation, and execution."""

import json
import logging
import re
from typing import Any, Optional

import google.auth
import httpx

BIGQUERY_MCP_URL = "https://bigquery.googleapis.com/mcp"

logger = logging.getLogger(__name__)


class MCPService:
    """Service for interacting with BigQuery via Gemini and BigQuery MCP."""

    def __init__(self):
        """Initialize MCP service with Gemini and BigQuery MCP."""
        logger.info("Initializing MCP service...")
        try:
            credentials, self.project_id = google.auth.default(
                scopes=["https://www.googleapis.com/auth/bigquery"]
            )
            logger.info(f"Using project: {self.project_id}")

            # Store credentials for MCP calls
            self.credentials = credentials

            # Configure Gemini for Vertex AI
            import vertexai
            import os

            os.environ["GOOGLE_CLOUD_PROJECT"] = self.project_id
            vertexai.init(project=self.project_id, location="global")
            from vertexai.generative_models import GenerativeModel

            # Create Gemini model for SQL generation
            self.gemini_model = GenerativeModel("gemini-3-pro-preview")

            logger.info("MCP service configured successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MCP service: {e}", exc_info=True)
            raise

    async def generate_sql_from_natural_language(self, description: str) -> dict[str, Any]:
        """
        Generate parameterized SQL from natural language using BigQuery MCP and Gemini.

        Step 1: Use Gemini to extract table references from natural language
        Step 2: Get table schema from BigQuery MCP get_table_info endpoint
        Step 3: Use Gemini to generate SQL with schema context
        Step 4: Extract parameters based on user intent

        Args:
            description: Natural language description of the query

        Returns:
            dict with 'sql' (the generated SQL) and 'parameters' (detected parameters)
        """
        logger.info(f"Generating SQL from description: {description}")

        try:
            schema_context = ""

            # Step 1: Extract ALL table references from natural language using Gemini
            extraction_prompt = f"""Extract ALL BigQuery table references from the following query description.
Return the table references as a JSON array. Each table reference should be in one of these formats:
- "project_id.dataset_id.table_id" (if project is mentioned)
- "dataset_id.table_id" (if only dataset and table are mentioned)
- "table_id" (if only table is mentioned)

If no tables are mentioned, return an empty array: []

Return ONLY a valid JSON array, nothing else. Examples:
- ["orders"]
- ["customers", "orders"]
- ["my-project.sales.orders", "my-project.sales.customers"]

Query description: {description}

Table references (JSON array):"""

            logger.debug("Extracting table references using Gemini")
            extraction_response = self.gemini_model.generate_content(extraction_prompt)
            table_refs_text = extraction_response.text.strip()

            logger.info(f"Extracted table references: {table_refs_text}")

            # Parse the JSON array of table references
            try:
                table_refs = json.loads(table_refs_text)
                if not isinstance(table_refs, list):
                    logger.warning(f"Expected list but got {type(table_refs)}, treating as single table")
                    table_refs = [table_refs_text] if table_refs_text else []
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse table references as JSON, treating as single table")
                # Fallback: treat as single table if not valid JSON
                table_refs = [table_refs_text] if table_refs_text and table_refs_text.upper() != "NONE" else []

            # Step 2: Get table schema from MCP for each table reference found
            if table_refs:
                schema_parts = []
                for table_ref in table_refs:
                    if not table_ref or str(table_ref).upper() == "NONE":
                        continue

                    try:
                        logger.info(f"Fetching schema for table: {table_ref}")
                        schema_info = await self._call_mcp_get_table_info(str(table_ref))
                        schema_parts.append(f"Table Schema for {table_ref}:\n{schema_info}")
                        logger.debug(f"Retrieved schema: {schema_info[:200]}...")
                    except Exception as e:
                        logger.warning(f"Could not fetch schema for {table_ref}: {e}")
                        continue

                # Combine all schemas into context
                if schema_parts:
                    schema_context = "\n\n" + "\n\n".join(schema_parts) + "\n"

            # Step 3: Create prompt for SQL generation with schema context
            prompt = f"""You are a SQL query generator for BigQuery.
Generate a parameterized BigQuery SQL query for the following request.

IMPORTANT RULES:
1. Use BigQuery parameter syntax with @ prefix (e.g., @start_date, @customer_id)
2. Return ONLY the SQL query, nothing else - no explanations, no markdown, no code blocks
3. Use proper BigQuery syntax and standard SQL
4. Make queries efficient and properly parameterized
5. For date parameters, use DATE type (@start_date)
6. For numeric IDs, use INT64 type (@customer_id)
7. For text fields, use STRING type (@product_name)
{schema_context}
User Request: {description}

Return only the SQL query:"""

            logger.debug("Calling Gemini to generate SQL with schema context")

            # Generate SQL using Gemini
            response = self.gemini_model.generate_content(prompt)
            sql_query = response.text

            # Clean up the SQL (remove markdown code blocks if present)
            sql_query = self._clean_sql(sql_query)

            logger.info(f"Generated SQL: {sql_query[:100]}...")

            # Step 4: Extract parameters from the generated SQL
            parameters = self._extract_parameters(sql_query)
            logger.info(f"Extracted {len(parameters)} parameters")

            return {"sql": sql_query.strip(), "parameters": parameters}

        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}", exc_info=True)
            raise Exception(f"Failed to generate SQL: {str(e)}")

    async def validate_and_test_query(
        self, sql_query: str, test_parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate SQL query using BigQuery MCP execute_sql endpoint (dry run).

        Args:
            sql_query: The SQL query to validate
            test_parameters: Dictionary of parameter names to test values

        Returns:
            dict with 'valid' (bool), 'results' (preview), 'error' (if any), and 'executed_query'
        """
        logger.info("Validating query via BigQuery MCP execute_sql")
        try:
            # Add LIMIT to query for testing
            limited_query = self._add_limit_to_query(sql_query)

            # Replace parameters with actual values for testing
            test_query = self._replace_parameters(limited_query, test_parameters)

            logger.debug(f"Test query: {test_query}")

            # Call MCP execute_sql endpoint
            result = await self._call_mcp_execute_sql(test_query)

            logger.info("Query validated successfully")
            return {
                "valid": True,
                "results": result,
                "error": None,
                "executed_query": test_query,
                "row_count": self._count_rows_in_results(result),
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Query validation failed: {error_msg}")
            return {
                "valid": False,
                "results": None,
                "error": error_msg,
                "executed_query": test_query if 'test_query' in locals() else sql_query,
            }

    async def execute_query(
        self, sql_query: str, parameters: dict[str, Any], max_results: int = 100
    ) -> dict[str, Any]:
        """
        Execute SQL query with parameters via BigQuery MCP.

        Args:
            sql_query: The SQL query to execute
            parameters: Dictionary of parameter names to values
            max_results: Maximum number of results to return

        Returns:
            dict with execution results
        """
        logger.info(f"Executing query with {len(parameters)} parameters")
        try:
            # Add LIMIT and replace parameters
            limited_query = self._add_limit_to_query(sql_query, max_results)
            final_query = self._replace_parameters(limited_query, parameters)

            logger.debug(f"Executing: {final_query}")

            # Call MCP execute_sql endpoint
            result = await self._call_mcp_execute_sql(final_query)

            logger.info("Query executed successfully")
            return {
                "success": True,
                "results": result,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Query execution failed: {e}", exc_info=True)
            return {"success": False, "results": None, "error": str(e)}

    async def _call_mcp_get_table_info(self, table_ref: str) -> str:
        """
        Call BigQuery MCP get_table_info endpoint to retrieve table schema.

        Args:
            table_ref: Table reference in format "project.dataset.table" or "dataset.table"

        Returns:
            Table schema information as formatted string
        """
        logger.debug(f"Calling MCP get_table_info for: {table_ref}")

        # Parse table reference
        parts = table_ref.split(".")
        if len(parts) == 2:
            dataset_id, table_id = parts
            project_id = self.project_id
        elif len(parts) == 3:
            project_id, dataset_id, table_id = parts
        else:
            raise ValueError(f"Invalid table reference: {table_ref}")

        # Prepare MCP request
        result = await self._call_mcp_tool(
            "get_table_info",
            {
                "project_id": project_id,
                "dataset_id": dataset_id,
                "table_id": table_id,
            },
        )

        return result

    async def _call_mcp_execute_sql(self, sql_query: str) -> str:
        """
        Call BigQuery MCP execute_sql endpoint to execute/validate SQL query.

        Args:
            sql_query: The SQL query to execute

        Returns:
            Query results as formatted string
        """
        logger.debug(f"Calling MCP execute_sql")

        result = await self._call_mcp_tool(
            "execute_sql",
            {
                "query": sql_query,
                "projectId": self.project_id,
                "dryRun": True
            },
        )

        # Format the result for better display
        return self._format_mcp_result(result)

    def _format_mcp_result(self, result: str) -> str:
        """
        Format MCP result for display in the GUI.

        Args:
            result: Raw result string from MCP

        Returns:
            Formatted result string
        """
        try:
            # Try to parse as JSON
            result_data = json.loads(result)

            # Check if it's a schema response (dry run)
            if "schema" in result_data:
                schema = result_data["schema"]
                fields = schema.get("fields", [])

                formatted_lines = ["Query is valid! Schema:"]
                formatted_lines.append("")

                for field in fields:
                    field_name = field.get("name", "unknown")
                    field_type = field.get("type", "unknown")
                    field_mode = field.get("mode", "NULLABLE")
                    formatted_lines.append(f"  • {field_name}: {field_type} ({field_mode})")

                return "\n".join(formatted_lines)

            # Check if it's actual query results
            elif "rows" in result_data:
                rows = result_data.get("rows", [])
                formatted_lines = [f"Query returned {len(rows)} rows:"]
                formatted_lines.append("")

                # Display first few rows
                for i, row in enumerate(rows[:5]):
                    formatted_lines.append(f"Row {i+1}: {json.dumps(row, indent=2)}")

                if len(rows) > 5:
                    formatted_lines.append(f"... and {len(rows) - 5} more rows")

                return "\n".join(formatted_lines)

            # If neither, return formatted JSON
            else:
                return json.dumps(result_data, indent=2)

        except json.JSONDecodeError:
            # If not JSON, return as-is
            return result

    async def _call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """
        Call a BigQuery MCP tool via JSON-RPC protocol.

        Args:
            tool_name: Name of the MCP tool (e.g., "get_table_info", "execute_sql")
            arguments: Dictionary of arguments for the tool

        Returns:
            Tool result as string

        Raises:
            Exception: If the MCP call fails
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
                "name": tool_name,
                "arguments": arguments,
            },
        }

        logger.debug(f"MCP Request: {tool_name} with args: {arguments}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                BIGQUERY_MCP_URL,
                headers=headers,
                json=json_rpc_request,
            )

            # Parse JSON response first (even if status code is 4xx/5xx)
            try:
                result = response.json()
            except Exception as e:
                # If we can't parse JSON, raise with status code
                logger.error(f"Failed to parse MCP response: {e}, status: {response.status_code}")
                response.raise_for_status()
                raise Exception(f"Invalid JSON response from MCP: {str(e)}")

            logger.debug(f"MCP Response: {result}")

            # Check for JSON-RPC error (this contains the actual error message)
            if "error" in result:
                error_obj = result["error"]
                error_msg = error_obj.get("message", str(error_obj))
                # Include error code if available
                error_code = error_obj.get("code", "")
                full_error = f"MCP error ({error_code}): {error_msg}" if error_code else f"MCP error: {error_msg}"
                logger.error(f"JSON-RPC error: {full_error}")
                raise Exception(full_error)

            # Extract result from response
            if "result" in result:
                result_data = result["result"]

                # Check if the result indicates an error (BigQuery MCP specific)
                if isinstance(result_data, dict) and result_data.get("isError"):
                    if "content" in result_data and isinstance(result_data["content"], list):
                        error_text = result_data["content"][0].get("text", "Unknown error")
                        logger.error(f"BigQuery error: {error_text}")
                        raise Exception(f"BigQuery error: {error_text}")

                # Extract content
                if "content" in result_data:
                    content = result_data["content"]
                    if isinstance(content, list) and len(content) > 0:
                        if "text" in content[0]:
                            return content[0]["text"]
                    return str(content)

            # If we got here with a non-200 status, raise it now
            if response.status_code >= 400:
                logger.error(f"HTTP error {response.status_code} with no JSON-RPC error field")
                response.raise_for_status()

            return "Tool executed successfully"

    def _extract_parameters(self, sql_query: str) -> list[dict[str, Any]]:
        """
        Extract parameter definitions from SQL query.

        Returns list of parameter definitions with inferred types.
        """
        # Find all @parameter_name occurrences
        pattern = r"@(\w+)"
        param_names = set(re.findall(pattern, sql_query))

        parameters = []
        for param_name in sorted(param_names):
            # Try to infer type from context
            param_type = self._infer_parameter_type(sql_query, param_name)

            parameters.append(
                {
                    "name": param_name,
                    "type": param_type,
                    "description": f"Parameter: {param_name}",
                    "required": True,
                }
            )

        return parameters

    def _infer_parameter_type(self, sql_query: str, param_name: str) -> str:
        """
        Infer parameter type from SQL context.

        This is a simple heuristic-based approach.
        """
        param_lower = param_name.lower()

        # Date-related parameters
        if any(
            keyword in param_lower
            for keyword in ["date", "day", "month", "year", "start", "end"]
        ):
            if "time" in param_lower or "timestamp" in param_lower:
                return "TIMESTAMP"
            return "DATE"

        # ID parameters are usually INT64
        if "id" in param_lower:
            return "INT64"

        # Amount, price, value parameters are FLOAT64
        if any(
            keyword in param_lower
            for keyword in ["amount", "price", "value", "rate", "percent"]
        ):
            return "FLOAT64"

        # Boolean parameters
        if any(
            keyword in param_lower
            for keyword in ["is_", "has_", "active", "enabled", "flag"]
        ):
            return "BOOL"

        # Default to STRING
        return "STRING"

    def _add_limit_to_query(self, sql_query: str, limit: int = 10) -> str:
        """Add LIMIT clause to query if not present."""
        sql_upper = sql_query.upper()

        if "LIMIT" not in sql_upper:
            # Simple append if no ORDER BY at the end
            return f"{sql_query.rstrip(';')} LIMIT {limit}"

        return sql_query

    def _count_rows_in_results(self, results_text: str) -> int:
        """Count number of rows in results (rough estimate)."""
        lines = results_text.strip().split("\n")
        # Subtract header lines (usually 2-3 lines)
        return max(0, len(lines) - 3)

    def _clean_sql(self, sql_query: str) -> str:
        """
        Clean SQL query by removing markdown code blocks and extra whitespace.

        Args:
            sql_query: Raw SQL query possibly with markdown

        Returns:
            Clean SQL query
        """
        # Remove markdown code blocks
        sql_query = re.sub(r"```sql\s*", "", sql_query)
        sql_query = re.sub(r"```\s*", "", sql_query)

        # Remove leading/trailing whitespace
        sql_query = sql_query.strip()

        return sql_query

    def _replace_parameters(self, sql_query: str, parameters: dict[str, Any]) -> str:
        """
        Replace @parameters in SQL query with actual values.

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
                # This handles cases where "2024" or "1.5" come from JavaScript
                try:
                    # Try integer first
                    if '.' not in value:
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
                # Other types - convert to string without quotes
                formatted_value = str(value)

            # Replace @param_name with the formatted value
            result = re.sub(
                f"@{param_name}\\b",
                formatted_value,
                result,
                flags=re.IGNORECASE,
            )

        return result
