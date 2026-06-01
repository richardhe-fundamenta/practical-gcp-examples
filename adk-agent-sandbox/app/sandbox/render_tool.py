import json

from google.adk.tools import ToolContext
from google.genai import types

from app.config import get_settings
from app.bigquery.sql_tool import VALIDATED_ROWS_KEY
from app.sandbox.client import run_in_sandbox, SandboxError

CHART_ARTIFACT_NAME = "chart.png"


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
        png = run_in_sandbox(
            code=code,
            data_json=data_json,
            out_name="output.png",
            resource_name=s.sandbox_resource_name,
        )
    except SandboxError as e:
        return {"status": "error", "error": str(e)}

    # Save as an ADK artifact: surfaced to the dev-ui and converted by the A2A layer into a
    # FilePart (image/png) for A2A clients (e.g. Gemini Enterprise). No base64 in the reply.
    await tool_context.save_artifact(
        filename=CHART_ARTIFACT_NAME,
        artifact=types.Part(inline_data=types.Blob(mime_type="image/png", data=png)),
    )
    return {"status": "ok", "artifact": CHART_ARTIFACT_NAME}
