import asyncio

from app.agent import skill_toolset


def test_python_runner_registered_lazily():
    # Skill is registered by name (description loaded); content is fetched at runtime.
    assert "python-runner" in skill_toolset._skills


def test_progressive_disclosure_tools_present():
    tools = asyncio.run(skill_toolset.get_tools())
    names = {t.name for t in tools}
    # list_skills exposes names+descriptions; load_skill fetches full SKILL.md on demand.
    assert {"list_skills", "load_skill"} <= names
