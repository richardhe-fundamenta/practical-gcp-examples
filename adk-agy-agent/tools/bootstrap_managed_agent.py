"""One-off bootstrap for the managed skills agent.

Creates (or patches) a single managed agent that mounts the WHOLE skills bucket
at /.agent. Because the sandbox loads skills from GCS on demand, new skills
dropped into the bucket appear automatically with no further calls — so this runs
ONCE at provisioning time (Terraform local-exec or a manual/CI invocation), never
per skill and never per interaction.

Shapes verified against the live API — see docs/NOTES-platform-api.md.

Usage:
    GOOGLE_CLOUD_PROJECT=... SKILLS_BUCKET=... uv run python tools/bootstrap_managed_agent.py
"""
from __future__ import annotations

import os
import sys
import time

HOST = "https://aiplatform.googleapis.com/v1beta1"
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
#
# SECURITY NOTE: ideally egress would be locked down (or disabled). Verified
# 2026-06-07 that the Managed Agents preview does NOT allow this whenever ANY data
# source (skills) is mounted — GCS *and* Skill Registry both fail identically:
#   "Network allowlist domain must be set when data source is set."  (allowlist required)
#   "Only domain: '*' is supported now."                              (specific domains rejected)
# So with skills mounted, "*" is the only accepted value; network can only be
# disabled on an agent with no skills at all. Tighten this the moment the platform
# supports domain allowlists.
DEFAULT_ALLOWLIST = "*"


def build_agent_body(
    bucket: str, agent_id: str, network_allowlist: str = DEFAULT_ALLOWLIST
) -> dict:
    """The Agent resource body for a whole-bucket skills mount.

    `base_environment.type` must be "remote"; source `type` is the uppercase enum
    "GCS". `network.allowlist` is the sandbox's egress allowlist (comma-separated
    domains, one entry each). See SECURITY NOTE above re: the "*"-only limitation.
    """
    domains = [d.strip() for d in network_allowlist.split(",") if d.strip()]
    return {
        "id": agent_id,
        "base_agent": BASE_AGENT,
        "system_instruction": SYSTEM_INSTRUCTION,
        "tools": DEFAULT_TOOLS,
        "base_environment": {
            "type": "remote",
            "sources": [
                {"type": "GCS", "source": f"gs://{bucket}", "target": "/.agent"}
            ],
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
    """Idempotent: create the agent if missing, else patch its config."""
    collection = f"{HOST}/projects/{project}/locations/{location}/agents"
    agent_url = f"{collection}/{agent_id}"
    if session.get(agent_url).status_code == 200:
        # Patch fields ONE AT A TIME: a combined update mask 400s, and "tools" is
        # not patchable at all (set only at create). Each single-field patch works.
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
    location = os.environ.get("MANAGED_AGENT_LOCATION", "global")
    bucket = os.environ["SKILLS_BUCKET"]
    agent_id = os.environ.get("MANAGED_AGENT_ID", "agy-skill-agent")
    allowlist = os.environ.get("MANAGED_AGENT_NETWORK_ALLOWLIST", DEFAULT_ALLOWLIST)

    body = build_agent_body(bucket, agent_id, allowlist)
    result = upsert(_session(), project, location, agent_id, body)
    print(f"managed agent '{agent_id}' {result} "
          f"(project={project}, location={location}, bucket={bucket})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
