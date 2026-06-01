from pathlib import Path
from app.skills.registry import discover_skills, load_skill_contract

SKILLS_ROOT = Path(__file__).resolve().parents[2] / "skills"
DEFAULT_SKILL = "analyst-chart-table"


def active_skill_contract(name: str = DEFAULT_SKILL, skills_root: Path = SKILLS_ROOT) -> str:
    """Return the full contract text (SKILL.md + available-packages) for the active skill.

    Progressive disclosure: callers list skills via discover_skills (name+description only);
    the full contract is loaded here only when a skill is activated.
    """
    for s in discover_skills(skills_root):
        if s.name == name:
            return load_skill_contract(s.path)
    raise ValueError(f"skill not found: {name!r} under {skills_root}")
