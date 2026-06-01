import json

from google.adk.tools import ToolContext
from google.genai import types

from app.config import get_settings
from app.bigquery.sql_tool import VALIDATED_ROWS_KEY
from app.sandbox.client import execute_in_sandbox, SandboxError

CHART_ARTIFACT_NAME = "chart.png"

# Session-state key under which render_chart records a pointer to the just-saved chart
# artifact ({"filename", "version"}). The after_agent_callback reads this and returns the
# artifact as an inline Part in the final response, because Gemini Enterprise only renders
# files returned inline — not files merely saved via save_artifact (adk-python#4273).
PENDING_CHART_KEY = "pending_chart_artifact"


async def render_chart(code: str, tool_context: ToolContext) -> dict:
    """Render a single chart in the isolated sandbox from the rows returned by your most
    recent successful run_validated_sql call, and save it as a viewable artifact.

    The harness writes those rows to ``data.json`` inside the sandbox as
    ``{"rows": [ ...record dicts... ]}``. Your code MUST read ``data.json`` and chart those
    rows. You cannot pass chart data directly — this guarantees the chart reflects only real,
    queried data (no fabrication).

    The resulting PNG is saved as the artifact ``chart.png`` and surfaced to the user/UI
    automatically (in the dev playground and, over A2A, to clients such as Gemini Enterprise
    as a file part). You therefore do NOT need to embed the image in your reply — just give
    the headline finding.

    Args:
        code: Python source (matplotlib Agg backend) that reads ``data.json`` (a dict with
              key ``"rows"``, a list of record dicts), shapes/aggregates the rows as needed,
              and writes a single chart to ``output.png``. Never hardcode data values.
    Returns:
        {"status":"ok","artifact":"chart.png"} or {"status":"error","error":"..."}.
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
        png = execute_in_sandbox(
            code=code,
            data_json=data_json,
            out_name="output.png",
            engine_name=s.agent_engine_name,
            tool_context=tool_context,
        )
    except SandboxError as e:
        return {"status": "error", "error": str(e)}

    # Save as an ADK artifact: surfaced to the dev-ui and persisted (GcsArtifactService).
    version = await tool_context.save_artifact(
        filename=CHART_ARTIFACT_NAME,
        artifact=types.Part(inline_data=types.Blob(mime_type="image/png", data=png)),
    )
    # Record a pointer so the after_agent_callback can return this artifact as an inline
    # Part in the final response — Gemini Enterprise renders inline Parts, not saved
    # artifacts (adk-python#4273).
    tool_context.state[PENDING_CHART_KEY] = {
        "filename": CHART_ARTIFACT_NAME,
        "version": version,
    }
    return {"status": "ok", "artifact": CHART_ARTIFACT_NAME}
