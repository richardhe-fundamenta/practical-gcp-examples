"""Read-only BigQuery schema-discovery toolset via the managed remote BQ MCP server.

Only the four schema-discovery tools are exposed; `execute_sql` is intentionally
filtered out — SQL execution goes through the `validate_and_run_sql` gate instead.

Bearer token is resolved once at toolset construction time from Application Default
Credentials.  For long-running servers see the bearer-token lifetime note below.
"""

import google.auth
import google.auth.transport.requests
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

_SCHEMA_TOOLS = [
    "list_dataset_ids",
    "list_table_ids",
    "get_dataset_info",
    "get_table_info",
]

_BQ_MCP_URL = "https://bigquery.googleapis.com/mcp"
_BQ_SCOPE = "https://www.googleapis.com/auth/bigquery"


def _bearer() -> str:
    """Obtain a fresh OAuth2 bearer token from Application Default Credentials."""
    creds, _ = google.auth.default(scopes=[_BQ_SCOPE])
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def bq_schema_toolset() -> McpToolset:
    """Return a read-only schema-discovery toolset backed by the managed remote
    BigQuery MCP server (Streamable HTTP transport, OAuth/IAM auth).

    Filtered so that only the four schema tools are exposed:
        list_dataset_ids, list_table_ids, get_dataset_info, get_table_info

    Note on bearer-token lifetime: the token is refreshed once when this
    function is called (at toolset construction).  Typical Google OAuth2 access
    tokens expire after ~1 hour.  For a long-running server, call this function
    again (or rebuild the toolset) before the token expires to avoid 401 errors.
    """
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=_BQ_MCP_URL,
            headers={"Authorization": f"Bearer {_bearer()}"},
        ),
        tool_filter=_SCHEMA_TOOLS,
    )
