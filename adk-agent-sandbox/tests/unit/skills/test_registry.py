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


def test_load_contract_includes_packages(tmp_path):
    sk = tmp_path / "s"
    (sk / "references").mkdir(parents=True)
    (sk / "SKILL.md").write_text("---\nname: s\ndescription: d\n---\nBODY\n")
    (sk / "references" / "available-packages.md").write_text("PKGS")
    text = load_skill_contract(sk)
    assert "BODY" in text and "PKGS" in text


def test_active_skill_contract_loads_real_skill():
    from app.skills.loader import active_skill_contract

    text = active_skill_contract()  # defaults to analyst-chart-table from the repo's skills/
    assert "analyst" in text.lower()
    assert "output.png" in text  # from the real SKILL.md Execution section
