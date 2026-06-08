from unittest.mock import MagicMock

from tools.bootstrap_managed_agent import (
    build_agent_body,
    discover_skill_ids,
    upsert,
)


def test_discover_skill_ids(tmp_path):
    (tmp_path / "echo").mkdir()
    (tmp_path / "echo" / "SKILL.md").write_text("---\nname: echo\n---\n")
    (tmp_path / "prime-factors").mkdir()
    (tmp_path / "prime-factors" / "SKILL.md").write_text("---\nname: prime-factors\n---\n")
    (tmp_path / "not-a-skill").mkdir()  # no SKILL.md -> ignored
    (tmp_path / "not-a-skill" / "readme.txt").write_text("x")
    assert discover_skill_ids(tmp_path) == ["echo", "prime-factors"]


def test_build_agent_body_uses_skill_registry_sources():
    body = build_agent_body(["echo", "prime-factors"], "P", "us-central1", "agy-skill-agent")
    assert body["id"] == "agy-skill-agent"
    assert body["base_agent"] == "antigravity-preview-05-2026"
    be = body["base_environment"]
    assert be["type"] == "remote"
    # one SKILL_REGISTRY source per skill; target is the parent dir (the registry
    # mounts each skill under <target>/<id>/), so all targets are /.agent/skills.
    assert be["sources"][0] == {
        "type": "SKILL_REGISTRY",
        "source": "projects/P/locations/us-central1/skills/echo",
        "target": "/.agent/skills",
    }
    assert {s["type"] for s in be["sources"]} == {"SKILL_REGISTRY"}
    assert [s["source"].split("/")[-1] for s in be["sources"]] == ["echo", "prime-factors"]
    assert {s["target"] for s in be["sources"]} == {"/.agent/skills"}
    # platform currently only accepts "*" for egress (see note in bootstrap)
    assert [a["domain"] for a in be["network"]["allowlist"]] == ["*"]


def test_build_agent_body_no_skills():
    body = build_agent_body([], "P", "us-central1", "agy-skill-agent")
    assert body["base_environment"]["sources"] == []


def test_upsert_creates_when_missing():
    session = MagicMock()
    session.get.side_effect = [MagicMock(status_code=404), MagicMock(status_code=200)]
    session.post.return_value = MagicMock(status_code=200)
    body = build_agent_body(["echo"], "P", "us-central1", "agy-skill-agent")
    assert upsert(session, "P", "global", "agy-skill-agent", body) == "created"
    assert session.post.called and not session.patch.called
    _, kwargs = session.post.call_args
    assert kwargs["json"]["id"] == "agy-skill-agent"


def test_upsert_patches_each_field_separately_when_exists():
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=200)  # already exists
    session.patch.return_value = MagicMock(status_code=200)
    body = build_agent_body(["echo"], "P", "us-central1", "agy-skill-agent")
    assert upsert(session, "P", "global", "agy-skill-agent", body) == "patched"
    assert not session.post.called
    masks = [kw["params"]["updateMask"] for _, kw in session.patch.call_args_list]
    assert masks == ["system_instruction", "base_environment"]
    for _, kw in session.patch.call_args_list:
        assert list(kw["json"].keys()) == [kw["params"]["updateMask"]]
