import base64

from a2a.types import FilePart, FileWithBytes, Message, Role, TextPart
from a2a.types import Part as A2APart
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from app.a2ui_support import MAX_UPLOAD_BYTES, _strip_oversized_parts
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


def _a2a_file_part(nbytes: int, name: str) -> A2APart:
    b64 = base64.b64encode(b"x" * nbytes).decode()
    return A2APart(root=FilePart(file=FileWithBytes(bytes=b64, mime_type="video/mp4", name=name)))


def test_strip_oversized_removes_blob_and_reports_it():
    # The executor strips over-cap file parts IN PLACE before the message is stored, so the blob
    # never lands in the Task history (echoed in the response) or reaches the model.
    text = A2APart(root=TextPart(text="analyse this"))
    big = _a2a_file_part(MAX_UPLOAD_BYTES + 1024, "clip.mp4")
    msg = Message(message_id="m1", role=Role.user, parts=[text, big])

    removed = _strip_oversized_parts(msg)
    assert [n for n, _ in removed] == ["clip.mp4"]
    assert msg.parts == [text]  # text kept, oversized blob gone


def test_strip_keeps_within_cap_files():
    small = _a2a_file_part(1024, "data.csv")
    msg = Message(message_id="m2", role=Role.user, parts=[small])
    assert _strip_oversized_parts(msg) == []
    assert msg.parts == [small]
