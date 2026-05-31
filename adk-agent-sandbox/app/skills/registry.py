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
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        f = d / "SKILL.md"
        if f.exists():
            fm = _frontmatter(f.read_text())
            out.append(SkillInfo(fm.get("name", d.name), fm.get("description", ""), d))
    return out


def load_skill_contract(skill_path: Path) -> str:
    body = (skill_path / "SKILL.md").read_text()
    pkgs = skill_path / "references" / "available-packages.md"
    if pkgs.exists():
        body += "\n\n## Available packages\n" + pkgs.read_text()
    return body
