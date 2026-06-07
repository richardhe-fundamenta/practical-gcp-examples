"""Calls the managed agent via the Interactions API; degrades gracefully.

Managed-agent interactions run with ``background=true`` (required), so this
creates an interaction and polls it to completion. Shapes verified against the
live API — see docs/NOTES-platform-api.md.
"""
from __future__ import annotations

import time

import google.auth
from google.auth.transport.requests import AuthorizedSession

from . import config, platform_api

NO_AGENT_MESSAGE = (
    "The skills environment isn't ready yet — the managed agent hasn't been "
    "provisioned. Run the bootstrap, then try again."
)
TRANSIENT_MESSAGE = (
    "The skills environment is temporarily unavailable. Please try again shortly."
)
PERMISSION_MESSAGE = (
    "I don't have permission to reach the skills environment. Please check the "
    "agent's IAM configuration."
)
TIMEOUT_MESSAGE = (
    "The skill task is taking longer than expected and hasn't finished yet. "
    "Please try again."
)

_TERMINAL = {"completed", "failed", "cancelled", "incomplete", "budget_exceeded"}


def classify_error(status_code: int) -> str:
    if status_code == 404:
        return NO_AGENT_MESSAGE
    if status_code in (401, 403):
        return PERMISSION_MESSAGE
    return TRANSIENT_MESSAGE


def _session():
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(creds)


def _extract_answer(interaction: dict) -> str:
    """All assistant text from the REST ``outputs`` stream, in order.

    ``outputs`` is a flat list of items with a ``type``: ``text`` items hold a
    plain-string ``text``; ``function_call``/``function_result`` are tool
    activity. The agent interleaves narration, tool calls, and the answer with no
    machine-readable "final answer" marker — and may run a tool (e.g. cleanup)
    *after* stating the result — so we return all text joined and let the caller
    (the ADK root agent) summarise. See docs/NOTES-platform-api.md.
    """
    blocks = _text_blocks(interaction.get("outputs") or [])
    return "\n".join(blocks).strip() or "(the skill produced no text output)"


def _text_blocks(outputs: list) -> list[str]:
    """Consolidated text blocks, dropping streaming partials.

    The ``outputs`` stream contains incremental text deltas followed by their
    consolidated block, so a block is kept only if it is not contained in a later
    text block (which also removes exact duplicates)."""
    texts = [
        i["text"].strip()
        for i in outputs
        if i.get("type") == "text" and i.get("text", "").strip()
    ]
    return [t for idx, t in enumerate(texts) if not any(t in later for later in texts[idx + 1:])]


def _clip(text: str, limit: int = 300) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "…"


def _clean_output(raw) -> str:
    """Strip the sandbox's [STDOUT]/[STDERR] wrappers to the meaningful output."""
    s = str(raw)
    if "[STDOUT]" in s:
        s = s.split("[STDOUT]", 1)[1]
    if "[STDERR]" in s:
        out, err = s.split("[STDERR]", 1)
        s = out if out.strip() else f"(stderr) {err}"
    return " ".join(s.split())


def _friendly_call(name: str, args: dict) -> str:
    """Human-readable description of a tool call (no raw JSON)."""
    a = args or {}
    path = a.get("AbsolutePath") or a.get("TargetFile") or a.get("DirectoryPath") or a.get("Path")
    cmd = a.get("CommandLine") or a.get("command")
    mapping = {
        "list_dir": f"📂 Listing {path or 'a directory'}",
        "view_file": f"📄 Reading {path or 'a file'}",
        "read_file": f"📄 Reading {path or 'a file'}",
        "create_file": f"📝 Writing {path or 'a file'}",
        "edit_file": f"✏️ Editing {path or 'a file'}",
        "delete_file": f"🗑️ Deleting {path or 'a file'}",
        "run_command": f"▶️ Running: {cmd or 'a command'}",
    }
    return mapping.get(name, f"🔧 {name}")


def _friendly_result(name: str, result) -> str:
    """Human-readable description of a tool result (no raw JSON)."""
    if isinstance(result, dict):
        if "Output" in result:                       # run_command
            return _clip(_clean_output(result.get("Output")), 200) or "(no output)"
        if isinstance(result.get("results"), list):  # list_dir
            names = [r.get("name") for r in result["results"] if isinstance(r, dict) and r.get("name")]
            return "found: " + ", ".join(names) if names else "(empty)"
        if result.get("Status"):                     # create/delete/edit
            return str(result["Status"])
        if "content" in result:                      # view_file
            return "(file read)"
    return _clip(result, 200)


def _format_transcript(interaction: dict) -> str:
    """A readable, de-duplicated trace of what the managed agent did: reasoning,
    tool calls, and tool results, in order (from the REST ``outputs`` stream)."""
    outputs = interaction.get("outputs") or []
    keep_text = set(_text_blocks(outputs))
    emitted: set[str] = set()
    lines = []
    for item in outputs:
        t = item.get("type")
        if t == "text":
            text = item.get("text", "").strip()
            if text in keep_text and text not in emitted:
                emitted.add(text)
                lines.append(f"💭 {_clip(text)}")
        elif t == "function_call":
            lines.append(_friendly_call(item.get("name", "tool"), item.get("arguments") or {}))
        elif t == "function_result":
            lines.append(f"   ↳ {_friendly_result(item.get('name', ''), item.get('result'))}")
    return "\n".join(lines)


def run_skill_task(prompt: str, tool_context) -> str:
    """Delegate a task to the managed skills agent and return its text result.

    Args:
        prompt: a clear, self-contained instruction to run against the mounted skills.
    """
    # Credentials / session — degrade rather than crash.
    try:
        session = _session()
    except Exception:
        return PERMISSION_MESSAGE

    # Preflight: is the managed agent provisioned?
    try:
        pre = session.get(
            platform_api.agent_url(
                config.PROJECT, config.LOCATION, config.MANAGED_AGENT_ID
            )
        )
    except Exception:
        return TRANSIENT_MESSAGE
    if pre.status_code != 200:
        return classify_error(pre.status_code)

    # Create a background interaction.
    body = {
        "input": prompt,
        "agent": config.MANAGED_AGENT_ID,
        "background": True,
        "store": True,
    }
    # Continuity within an ADK session: chain the conversation via
    # previous_interaction_id, and reuse the same sandbox via environment.env_id
    # (verified field shape) so files/state persist across turns.
    prev = tool_context.state.get("previous_interaction_id")
    if prev:
        body["previous_interaction_id"] = prev
    env = tool_context.state.get("environment_id")
    if env:
        body["environment"] = {"env_id": env}

    try:
        resp = session.post(
            platform_api.interactions_url(config.PROJECT, config.LOCATION),
            json=body,
            timeout=config.INTERACT_TIMEOUT_S,
        )
    except Exception:
        return TRANSIENT_MESSAGE
    if resp.status_code != 200:
        return classify_error(resp.status_code)
    interaction_id = resp.json().get("id")
    if not interaction_id:
        return TRANSIENT_MESSAGE

    # Poll to completion.
    poll_url = platform_api.interaction_url(
        config.PROJECT, config.LOCATION, interaction_id
    )
    deadline = time.monotonic() + config.INTERACT_TIMEOUT_S
    data: dict = {}
    status = ""
    while time.monotonic() < deadline:
        try:
            g = session.get(poll_url)
        except Exception:
            return TRANSIENT_MESSAGE
        if g.status_code != 200:
            return classify_error(g.status_code)
        data = g.json()
        status = str(data.get("status", "")).lower()
        if status in _TERMINAL:
            break
        time.sleep(config.POLL_INTERVAL_S)
    else:
        return TIMEOUT_MESSAGE

    # Persist continuity for multi-turn.
    if data.get("id"):
        tool_context.state["previous_interaction_id"] = data["id"]
    if data.get("environment_id"):
        tool_context.state["environment_id"] = data["environment_id"]

    if status != "completed":
        return f"The skill task ended with status '{status}'. Please try again."

    answer = _extract_answer(data)
    if config.SHOW_STEPS:
        transcript = _format_transcript(data)
        if transcript:
            # Chronological trace (reasoning + tool calls + results); the final
            # answer text is the closing line(s). No separate answer block — that
            # would duplicate the text already in the trace.
            return (
                "Trace of what the skills agent did (💭 reasoning, 🔧 tool call, "
                f"↪ result):\n{transcript}"
            )
    return answer
