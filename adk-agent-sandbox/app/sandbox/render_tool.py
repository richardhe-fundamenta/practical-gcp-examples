import base64
from app.config import get_settings
from app.sandbox.client import run_in_sandbox, SandboxError


def render_chart(code: str, data_json: str) -> dict:
    """Run model-generated Python rendering code in the isolated sandbox over data_json
    and return the resulting PNG.

    Args:
        code: Python source that reads 'data.json' and writes 'output.png' (matplotlib Agg).
        data_json: JSON string exposed to the code as 'data.json'.
    Returns:
        {"status":"ok","png_base64": "..."} or {"status":"error","error":"..."}.
    """
    s = get_settings()
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
