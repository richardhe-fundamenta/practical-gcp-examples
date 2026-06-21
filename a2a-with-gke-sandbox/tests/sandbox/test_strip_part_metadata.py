from google.genai import types
from google.adk.models.llm_request import LlmRequest

from app.agent import _before_model


def test_strips_part_metadata_from_all_parts():
    # A2A-sourced parts arrive with part_metadata set; Vertex rejects it.
    p1 = types.Part(text="hi", part_metadata={"adk_type": "text"})
    p2 = types.Part(text="more", part_metadata={"x": 1})
    req = LlmRequest(contents=[types.Content(role="user", parts=[p1, p2])])

    assert _before_model(None, req) is None  # proceed normally
    for content in req.contents:
        for part in content.parts:
            assert part.part_metadata is None


def test_no_metadata_is_noop():
    req = LlmRequest(contents=[types.Content(role="user", parts=[types.Part(text="hi")])])
    assert _before_model(None, req) is None
    assert req.contents[0].parts[0].part_metadata is None


def test_advertises_uploaded_filenames():
    blob = types.Blob(data=b"col\n1\n", mime_type="text/csv", display_name="data.csv")
    req = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part(inline_data=blob)])]
    )
    assert _before_model(None, req) is None
    assert "data.csv" in str(req.config.system_instruction)
