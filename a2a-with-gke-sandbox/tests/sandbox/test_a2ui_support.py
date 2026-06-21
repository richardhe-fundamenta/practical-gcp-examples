import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import app.a2ui_support as a2ui

from a2ui.parser.payload_fixer import parse_and_fix

from app.a2ui_support import (
    _A2UI_EXAMPLES,
    _DEFAULT_CATALOG,
    URL_MAP_KEY,
    build_a2ui_toolset,
    setup_a2ui_state,
    substitute_a2ui_urls,
)


def test_shipped_a2ui_example_is_valid_v08():
    # The example we inject into the system prompt must be valid against the v0.8 catalog —
    # otherwise we'd be teaching the model a broken payload.
    raw = _A2UI_EXAMPLES[_A2UI_EXAMPLES.index("Example"):]  # skip prose brackets
    payload = parse_and_fix(raw[raw.index("[") : raw.rindex("]") + 1])
    _DEFAULT_CATALOG.validator.validate(payload)  # raises on invalid


def test_substitute_a2ui_urls_swaps_token_in_tool_args():
    # before_tool_callback rewrites the model's a2ui_json, replacing the placeholder token with
    # the real signed URL from live tool state.
    tool = SimpleNamespace(name="send_a2ui_json_to_client")
    args = {"a2ui_json": '[{"Image": {"url": {"literalString": "{{chart:chart.png}}"}}}]'}
    ctx = SimpleNamespace(state={URL_MAP_KEY: {"{{chart:chart.png}}": "https://real/signed.png"}})
    assert substitute_a2ui_urls(tool, args, ctx) is None
    assert "https://real/signed.png" in args["a2ui_json"]
    assert "{{chart" not in args["a2ui_json"]


def test_substitute_a2ui_urls_ignores_other_tools():
    tool = SimpleNamespace(name="run_code")
    args = {"code": "print('{{chart:chart.png}}')"}
    ctx = SimpleNamespace(state={URL_MAP_KEY: {"{{chart:chart.png}}": "https://real/signed.png"}})
    substitute_a2ui_urls(tool, args, ctx)
    assert args["code"] == "print('{{chart:chart.png}}')"


def test_event_converter_accepts_the_5_positional_call():
    # ADK's event-converter dispatch passes part_converter_func as a 5th positional arg;
    # the converter must accept it (regression: it used **kwargs and crashed).
    conv = a2ui._A2uiEventConverter()
    ctx = SimpleNamespace(session=SimpleNamespace(state={}))
    with patch.object(a2ui, "convert_event_to_a2a_events", return_value=["ok"]) as m:
        out = conv(object(), ctx, "task", "ctx", lambda p: [])
    assert out == ["ok"] and m.called


def test_send_tool_hidden_until_state_enabled():
    ts = build_a2ui_toolset()

    # Before setup_a2ui_state runs, the toolset exposes no tools.
    off = asyncio.run(ts.get_tools(SimpleNamespace(state={})))
    assert [t.name for t in off] == []

    # The before_agent_callback enables A2UI + loads the catalog into state.
    cb = SimpleNamespace(state={})
    setup_a2ui_state(cb)
    assert cb.state["system:a2ui_enabled"] is True
    assert cb.state["system:a2ui_catalog"] is not None

    on = asyncio.run(ts.get_tools(SimpleNamespace(state=cb.state)))
    assert "send_a2ui_json_to_client" in [t.name for t in on]
