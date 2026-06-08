# /// script
# requires-python = ">=3.10"
# dependencies = ["google-auth", "requests"]
# ///
"""One-off bootstrap for the managed skills agent (Skill Registry edition).

Creates (or patches) a single managed agent that mounts each skill registered in
the Skill Registry as a read-only source. Skills are registered from the repo
skills/ folder by tools/register_skills.py (run that first). Re-run this whenever
the set of skills changes — it reconciles the agent's base_environment.sources.

Agents live at the GLOBAL endpoint; Skill Registry skills are regional
(us-central1). A global agent can reference a regional skill.

Shapes verified against the live API — see git history / README.

Usage:
    GOOGLE_CLOUD_PROJECT=... uv run tools/bootstrap_managed_agent.py
"""
from __future__ import annotations

import os
import pathlib
import sys
import time

HOST = "https://aiplatform.googleapis.com/v1beta1"  # agents: global endpoint
BASE_AGENT = "antigravity-preview-05-2026"
SYSTEM_INSTRUCTION = (
    "You are a skills execution agent. Use the skills mounted under "
    "/.agent/skills to accomplish the user's task. Inspect each skill's SKILL.md "
    "to decide which to apply, then carry out the task. "
    "Your final reply MUST state the direct answer or result to the user's "
    "request — including any value your code computed or printed (quote the exact "
    "output). Do NOT reply with only a summary of the steps you took."
)
DEFAULT_TOOLS = [
    {"type": "code_execution"},
    {"type": "google_search"},
    {"type": "url_context"},
]

# Sandbox network egress allowlist (comma-separated domains; each → one entry).
# The preview only accepts "*" whenever any skill source is mounted (specific
# domains are rejected). Configurable for when the platform supports allowlists.
DEFAULT_ALLOWLIST = "*"


SKILLS_HOST_TMPL = "https://{loc}-aiplatform.googleapis.com/v1beta1"


def _skill_exists(session, project: str, skills_location: str, skill_id: str) -> bool:
    """True if the skill is registered (so it's safe to mount)."""
    url = (
        f"{SKILLS_HOST_TMPL.format(loc=skills_location)}"
        f"/projects/{project}/locations/{skills_location}/skills/{skill_id}"
    )
    return session.get(url).status_code == 200


def discover_skill_ids(skills_dir: str | pathlib.Path) -> list[str]:
    """Skill IDs = names of skills_dir subfolders that contain a SKILL.md."""
    root = pathlib.Path(skills_dir)
    if not root.is_dir():
        return []
    return sorted(
        p.name for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()
    )


def build_agent_body(
    skill_ids: list[str],
    project: str,
    skills_location: str,
    agent_id: str,
    network_allowlist: str = DEFAULT_ALLOWLIST,
) -> dict:
    """Agent resource body mounting each registered skill as a SKILL_REGISTRY source.

    base_environment.type must be "remote"; each source references a Skill Registry
    resource (projects/<p>/locations/<skills_location>/skills/<id>) mounted read-only
    at /.agent/skills/<id>. network.allowlist defaults to "*" (see note above).
    """
    domains = [d.strip() for d in network_allowlist.split(",") if d.strip()]
    # The registry mounts each skill UNDER target as <target>/<id>/, so the target
    # is the parent dir (/.agent/skills) — NOT /.agent/skills/<id> (that double-nests
    # to /.agent/skills/<id>/<id>/ and makes the agent hunt for SKILL.md every turn).
    sources = [
        {
            "type": "SKILL_REGISTRY",
            "source": f"projects/{project}/locations/{skills_location}/skills/{sid}",
            "target": "/.agent/skills",
        }
        for sid in skill_ids
    ]
    return {
        "id": agent_id,
        "base_agent": BASE_AGENT,
        "system_instruction": SYSTEM_INSTRUCTION,
        "tools": DEFAULT_TOOLS,
        "base_environment": {
            "type": "remote",
            "sources": sources,
            "network": {"allowlist": [{"domain": d} for d in domains]},
        },
    }


def _session():
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(creds)


def _wait_ready(session, agent_url: str, timeout_s: int = 120) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if session.get(agent_url).status_code == 200:
            return
        time.sleep(3)
    raise TimeoutError(f"agent did not become ready within {timeout_s}s: {agent_url}")


def upsert(session, project: str, location: str, agent_id: str, body: dict) -> str:
    """Idempotent: create the agent if missing, else patch its config.

    Patch fields ONE AT A TIME: a combined update mask 400s, and "tools" is not
    patchable (set only at create). Each single-field patch works.
    """
    collection = f"{HOST}/projects/{project}/locations/{location}/agents"
    agent_url = f"{collection}/{agent_id}"
    if session.get(agent_url).status_code == 200:
        for field in ("system_instruction", "base_environment"):
            resp = session.patch(
                agent_url, params={"updateMask": field}, json={field: body[field]}
            )
            resp.raise_for_status()
        return "patched"
    resp = session.post(collection, json=body)  # id travels in the body
    resp.raise_for_status()
    _wait_ready(session, agent_url)
    return "created"


def main() -> int:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    agent_location = os.environ.get("MANAGED_AGENT_LOCATION", "global")
    skills_location = os.environ.get("SKILLS_LOCATION", "us-central1")
    agent_id = os.environ.get("MANAGED_AGENT_ID", "agy-skill-agent")
    allowlist = os.environ.get("MANAGED_AGENT_NETWORK_ALLOWLIST", DEFAULT_ALLOWLIST)
    skills_dir = os.environ.get("SKILLS_DIR", "skills")

    session = _session()
    discovered = discover_skill_ids(skills_dir)
    # Only mount skills that are actually registered (skip e.g. ids reserved after
    # a recent delete) — referencing a missing skill would break the agent patch.
    skill_ids = [
        sid for sid in discovered if _skill_exists(session, project, skills_location, sid)
    ]
    skipped = [s for s in discovered if s not in skill_ids]
    body = build_agent_body(skill_ids, project, skills_location, agent_id, allowlist)
    result = upsert(session, project, agent_location, agent_id, body)
    print(
        f"managed agent '{agent_id}' {result} (project={project}, "
        f"skills={skill_ids or 'none'} from {skills_location})"
    )
    if skipped:
        print(f"NOTE: not in registry, not mounted: {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
