from unittest.mock import MagicMock

from tools.bootstrap_managed_agent import build_agent_body, upsert


def test_build_agent_body_whole_bucket_mount():
    body = build_agent_body("my-bucket", "agy-skill-agent")
    assert body["id"] == "agy-skill-agent"
    assert body["base_agent"] == "antigravity-preview-05-2026"
    be = body["base_environment"]
    assert be["type"] == "remote"
    # single whole-bucket source, uppercase GCS enum, mounted at /.agent
    assert be["sources"] == [
        {"type": "GCS", "source": "gs://my-bucket", "target": "/.agent"}
    ]
    # platform currently only accepts "*" for the egress allowlist (see SECURITY NOTE)
    assert [a["domain"] for a in be["network"]["allowlist"]] == ["*"]


def test_upsert_creates_when_missing():
    session = MagicMock()
    # GET agent -> 404 (missing); after create, _wait_ready GET -> 200
    session.get.side_effect = [
        MagicMock(status_code=404),
        MagicMock(status_code=200),
    ]
    session.post.return_value = MagicMock(status_code=200)
    result = upsert(session, "P", "global", "agy-skill-agent", {"id": "agy-skill-agent"})
    assert result == "created"
    assert session.post.called
    assert not session.patch.called
    # id is carried in the POST body (no agentId query param)
    _, kwargs = session.post.call_args
    assert kwargs["json"]["id"] == "agy-skill-agent"


def test_upsert_patches_each_field_separately_when_exists():
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=200)  # already exists
    session.patch.return_value = MagicMock(status_code=200)
    body = build_agent_body("my-bucket", "agy-skill-agent")
    result = upsert(session, "P", "global", "agy-skill-agent", body)
    assert result == "patched"
    assert not session.post.called
    # one PATCH per field (a combined update mask 400s on the live API)
    masks = [kw["params"]["updateMask"] for _, kw in session.patch.call_args_list]
    assert masks == ["system_instruction", "base_environment"]
    # each call sends only its own field
    for _, kw in session.patch.call_args_list:
        assert list(kw["json"].keys()) == [kw["params"]["updateMask"]]
