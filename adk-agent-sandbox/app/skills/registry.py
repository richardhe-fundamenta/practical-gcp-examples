from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    path: Path


def _frontmatter(md: str) -> dict:
    if md.startswith("---"):
        _, fm, _body = md.split("---", 2)
        return yaml.safe_load(fm) or {}
    return {}


def discover_skills(root: Path) -> list[SkillInfo]:
    out = []
    if not root.is_dir():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        f = d / "SKILL.md"
        if f.exists():
            fm = _frontmatter(f.read_text())
            out.append(SkillInfo(fm.get("name", d.name), fm.get("description", ""), d))
    return out


def _escape_braces(text: str) -> str:
    """Escape literal braces so ADK's instruction templating treats them as literals.

    ADK resolves ``{name}`` in an instruction as a session-state variable and raises
    KeyError if missing. Reference files (notably the example renderer's f-strings like
    ``{best}``) contain such braces; doubling them (``{{`` / ``}}``) is ADK's escape and
    renders back to single braces for the model.
    """
    return text.replace("{", "{{").replace("}", "}}")


def load_skill_contract(skill_path: Path) -> str:
    """Return the full activation text for a skill: SKILL.md followed by every file
    under references/ (sorted), each under a header derived from its filename.

    Loading all reference files means none are dead weight — output-contract.md,
    security-notes.md, available-packages.md and the example renderer all reach the
    model, and any new reference file is included automatically. Reference content has
    its braces escaped so f-strings / JSON examples don't break instruction templating.
    """
    parts = [(skill_path / "SKILL.md").read_text()]
    refs = skill_path / "references"
    if refs.is_dir():
        for ref in sorted(p for p in refs.iterdir() if p.is_file()):
            title = ref.stem.replace("-", " ").replace("_", " ").title()
            parts.append(
                f"## Reference: {title} ({ref.name})\n\n{_escape_braces(ref.read_text())}"
            )
    return "\n\n".join(parts)
