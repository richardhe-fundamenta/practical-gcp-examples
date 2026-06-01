"""Unit tests for the after_agent_callback that makes the chart render inline in Gemini
Enterprise.

GE only renders files returned as inline types.Part objects in the final agent response,
not files that are merely saved via tool_context.save_artifact() (adk-python#4273). So
render_chart stashes a pointer to the saved artifact in session state, and this callback
loads it and returns it as an inline image Part appended to the final response.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from google.genai import types

from app.render_callback import attach_chart_to_response
from app.sandbox.render_tool import PENDING_CHART_KEY

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


def _ctx(state):
    c = MagicMock()
    c.state = dict(state)
    c.load_artifact = AsyncMock()
    return c


def test_attaches_pending_chart_as_inline_image_and_clears_flag():
    ctx = _ctx({PENDING_CHART_KEY: {"filename": "chart.png", "version": 3}})
    ctx.load_artifact.return_value = types.Part(
        inline_data=types.Blob(mime_type="image/png", data=PNG)
    )

    out = asyncio.run(attach_chart_to_response(callback_context=ctx))

    assert isinstance(out, types.Content)
    assert len(out.parts) == 1
    assert out.parts[0].inline_data.mime_type == "image/png"
    assert out.parts[0].inline_data.data == PNG
    ctx.load_artifact.assert_awaited_once_with("chart.png", 3)
    assert ctx.state[PENDING_CHART_KEY] is None  # consumed so later turns don't re-attach


def test_no_pending_returns_none_and_does_not_load():
    ctx = _ctx({})

    out = asyncio.run(attach_chart_to_response(callback_context=ctx))

    assert out is None
    ctx.load_artifact.assert_not_called()


def test_pending_but_missing_artifact_returns_none_and_clears():
    ctx = _ctx({PENDING_CHART_KEY: {"filename": "chart.png", "version": 1}})
    ctx.load_artifact.return_value = None

    out = asyncio.run(attach_chart_to_response(callback_context=ctx))

    assert out is None
    assert ctx.state[PENDING_CHART_KEY] is None
