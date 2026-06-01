"""Read-only BigQuery schema-discovery toolset via the managed remote BQ MCP server.

Only the four schema-discovery tools are exposed; `execute_sql` is intentionally
filtered out — SQL execution goes through the `validate_and_run_sql` gate instead.

Auth: the OAuth2 bearer token is supplied per-request via a ``header_provider``
callable backed by cached Application Default Credentials that auto-refresh when
expired. This avoids the ~1h token-expiry 401s a long-running server would hit if
the token were baked into the connection params once at construction.
"""

from typing import Optional

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

_creds = None  # cached ADC credentials, refreshed on demand


def _token() -> str:
    """Return a valid OAuth2 bearer token, refreshing the cached creds if expired."""
    global _creds
    if _creds is None:
        _creds, _ = google.auth.default(scopes=[_BQ_SCOPE])
    if not _creds.valid:
        _creds.refresh(google.auth.transport.requests.Request())
    return _creds.token


def _auth_headers(_readonly_context=None) -> dict[str, str]:
    """header_provider callable: a fresh Authorization header for each MCP call."""
    return {"Authorization": f"Bearer {_token()}"}


def bq_schema_toolset() -> McpToolset:
    """Return a read-only schema-discovery toolset backed by the managed remote
    BigQuery MCP server (Streamable HTTP transport, OAuth/IAM auth).

    Filtered so that only the four schema tools are exposed:
        list_dataset_ids, list_table_ids, get_dataset_info, get_table_info
    """
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=_BQ_MCP_URL),
        header_provider=_auth_headers,
        tool_filter=_SCHEMA_TOOLS,
    )
