# /// script
# requires-python = ">=3.10"
# dependencies = ["google-auth", "requests", "pyyaml"]
# ///
"""Register the repo's skills/ folder into the Skill Registry (idempotent upsert).

Each skills/<id>/ folder (containing a SKILL.md, + optional scripts/, references/)
becomes a managed Skill resource. Skills are the source of truth in git; this
pushes them to the registry, which the managed agent then mounts read-only.

Usage (needs `gcloud auth application-default login`):
    uv run tools/register_skills.py

Env (optional):
    GOOGLE_CLOUD_PROJECT   default: rocketech-de-pgcp-sandbox
    SKILLS_LOCATION        default: us-central1  (registry is regional)
    SKILLS_DIR             default: skills
"""
from __future__ import annotations

import base64
import io
import os
import pathlib
import sys
import time
import zipfile

HOST_TMPL = "https://{loc}-aiplatform.googleapis.com/v1beta1"
TERMINAL_STATES = {"ACTIVE", "SKILL_STATE_ACTIVE", "FAILED", "SKILL_STATE_FAILED"}


def discover_skills(skills_dir: str | pathlib.Path) -> list[pathlib.Path]:
    """Skill folders = immediate subdirs of skills_dir that contain a SKILL.md."""
    root = pathlib.Path(skills_dir)
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def parse_frontmatter(skill_md: pathlib.Path) -> dict:
    """Return the YAML frontmatter of a SKILL.md (the block between --- ... ---)."""
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    import yaml  # lazy so the module imports without the dep (tests)

    return yaml.safe_load(text[3:end]) or {}


def zip_skill(skill_dir: str | pathlib.Path) -> bytes:
    """Zip a skill folder with files at the archive root (SKILL.md, scripts/, ...)."""
    root = pathlib.Path(skill_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for fp in sorted(root.rglob("*")):
            if fp.is_file():
                z.write(fp, fp.relative_to(root).as_posix())
    return buf.getvalue()


def build_skill_body(skill_dir: str | pathlib.Path) -> dict:
    """Skill resource body from a folder: displayName/description from SKILL.md
    frontmatter, zippedFilesystem = base64 of the zipped folder."""
    skill_dir = pathlib.Path(skill_dir)
    fm = parse_frontmatter(skill_dir / "SKILL.md")
    name = str(fm.get("name") or skill_dir.name)
    description = str(fm.get("description") or name).strip()
    return {
        "displayName": name,
        "description": description,
        "zippedFilesystem": base64.b64encode(zip_skill(skill_dir)).decode(),
    }


def _session():
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(creds)


def _wait_active(session, skill_url: str, timeout_s: int = 180) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        r = session.get(skill_url)
        if r.status_code == 200:
            state = r.json().get("state")
            if state in TERMINAL_STATES:
                return state or "ACTIVE"
        time.sleep(4)
    raise TimeoutError(f"skill not ready within {timeout_s}s: {skill_url}")


def upsert_skill(session, base: str, skill_id: str, body: dict) -> str:
    """Create the skill if missing, else update it. Returns 'created' or 'updated'."""
    skill_url = f"{base}/skills/{skill_id}"
    if session.get(skill_url).status_code == 200:
        resp = session.patch(
            skill_url,
            params={"updateMask": "display_name,description,zipped_filesystem"},
            json=body,
        )
        resp.raise_for_status()
        _wait_active(session, skill_url)
        return "updated"
    resp = session.post(f"{base}/skills", params={"skillId": skill_id}, json=body)
    if resp.status_code == 409:
        # Skill IDs are reserved for ~24h after deletion — can't recreate yet.
        return "reserved"
    resp.raise_for_status()
    _wait_active(session, skill_url)
    return "created"


def main() -> int:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "rocketech-de-pgcp-sandbox")
    location = os.environ.get("SKILLS_LOCATION", "us-central1")
    skills_dir = os.environ.get("SKILLS_DIR", "skills")

    dirs = discover_skills(skills_dir)
    if not dirs:
        print(f"no skills found under {skills_dir}/")
        return 0
    session = _session()
    base = f"{HOST_TMPL.format(loc=location)}/projects/{project}/locations/{location}"
    reserved = []
    for d in dirs:
        result = upsert_skill(session, base, d.name, build_skill_body(d))
        print(f"  {result}: {d.name}")
        if result == "reserved":
            reserved.append(d.name)
    print(f"processed {len(dirs)} skill(s) in {project}/{location}")
    if reserved:
        print(f"NOTE: id reserved ~24h after a prior delete (skipped): {reserved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
