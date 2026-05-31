import base64
import json

from google.adk.tools import ToolContext

from app.config import get_settings
from app.bigquery.sql_tool import VALIDATED_ROWS_KEY
from app.sandbox.client import run_in_sandbox, SandboxError


def render_chart(code: str, tool_context: ToolContext) -> dict:
    """Render a single chart in the isolated sandbox from the rows returned by your most
    recent successful run_validated_sql call.

    The harness writes those rows to ``data.json`` inside the sandbox as
    ``{"rows": [ ...record dicts... ]}``. Your code MUST read ``data.json`` and chart those
    rows. You cannot pass chart data directly — this guarantees the chart reflects only real,
    queried data (no fabrication).

    Args:
        code: Python source (matplotlib Agg backend) that reads ``data.json`` (a dict with
              key ``"rows"``, a list of record dicts), shapes/aggregates the rows as needed,
              and writes a single chart to ``output.png``. Never hardcode data values.
    Returns:
        {"status":"ok","png_base64": "..."} or {"status":"error","error":"..."}.
    """
    rows = tool_context.state.get(VALIDATED_ROWS_KEY)
    if not rows:
        return {
            "status": "error",
            "error": (
                "No validated query results available to chart. Call run_validated_sql and "
                "obtain a non-empty result first; do not fabricate data."
            ),
        }
    s = get_settings()
    data_json = json.dumps({"rows": rows})
    try:
        png = run_in_sandbox(
            code=code,
            data_json=data_json,
            out_name="output.png",
            resource_name=s.sandbox_resource_name,
        )
    except SandboxError as e:
        return {"status": "error", "error": str(e)}
    return {"status": "ok", "png_base64": base64.b64encode(png).decode()}
