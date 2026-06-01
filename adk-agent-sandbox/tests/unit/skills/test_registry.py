from pathlib import Path
from app.skills.registry import discover_skills, load_skill_contract


def test_discover_reads_name_and_description(tmp_path):
    sk = tmp_path / "analyst-chart-table"
    (sk / "references").mkdir(parents=True)
    (sk / "SKILL.md").write_text(
        "---\nname: analyst-chart-table\n"
        "description: chart+table\n---\n# body\n"
    )
    found = discover_skills(tmp_path)
    assert found[0].name == "analyst-chart-table"
    assert "chart" in found[0].description


def test_load_contract_includes_all_reference_files(tmp_path):
    sk = tmp_path / "s"
    (sk / "references").mkdir(parents=True)
    (sk / "SKILL.md").write_text("---\nname: s\ndescription: d\n---\nBODY\n")
    (sk / "references" / "available-packages.md").write_text("PKGS")
    (sk / "references" / "output-contract.md").write_text("CONTRACT")
    (sk / "references" / "security-notes.md").write_text("SECURITY")
    text = load_skill_contract(sk)
    assert "BODY" in text
    assert "PKGS" in text and "CONTRACT" in text and "SECURITY" in text


def test_load_contract_escapes_braces_in_references(tmp_path):
    """Reference braces (e.g. f-string {best}) must be neutralized so ADK instruction
    templating treats them as literal text, not session-state variables. ADK's regex
    strips doubled braces, so we insert a backslash inside each brace instead."""
    sk = tmp_path / "s"
    (sk / "references").mkdir(parents=True)
    (sk / "SKILL.md").write_text("---\nname: s\ndescription: d\n---\nBODY\n")
    (sk / "references" / "example_render.py").write_text('x = f"{best}"\n')
    text = load_skill_contract(sk)
    # No bare {identifier} survives that ADK would try to resolve as a state var
    assert "{best}" not in text
    assert "{\\best\\}" in text


def test_load_contract_without_references_dir(tmp_path):
    sk = tmp_path / "s"
    sk.mkdir()
    (sk / "SKILL.md").write_text("---\nname: s\ndescription: d\n---\nONLYBODY\n")
    assert load_skill_contract(sk).strip().endswith("ONLYBODY")


def test_active_skill_contract_loads_real_skill():
    from app.skills.loader import active_skill_contract

    text = active_skill_contract()  # defaults to analyst-chart-table from the repo's skills/
    assert "analyst" in text.lower()
    assert "output.png" in text  # from the real SKILL.md Execution section
