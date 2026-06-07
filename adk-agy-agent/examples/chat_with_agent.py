# /// script
# requires-python = ">=3.10"
# dependencies = ["google-genai>=2.8"]
# ///
"""Interactively chat directly with the managed skills agent — with LIVE streaming.

This talks straight to the Gemini Enterprise Agent Platform Interactions API via
the google-genai SDK and **streams** the agent's output as it is produced: you see
reasoning tokens, tool calls, and tool results arrive in real time (no waiting for
the whole turn to finish). It is a standalone `uv` script — the inline metadata
above pulls a newer google-genai than the main project pins, without affecting it.

Usage:
    uv run examples/chat_with_agent.py                 # interactive REPL (streaming)
    uv run examples/chat_with_agent.py "your prompt"   # one-shot (streaming)
    SHOW_TOOLS=0 uv run examples/chat_with_agent.py    # stream text only, hide tool steps

Environment (all optional, with defaults):
    GOOGLE_CLOUD_PROJECT     default: rocketech-de-pgcp-sandbox
    MANAGED_AGENT_LOCATION   default: global   (must be 'global')
    MANAGED_AGENT_ID         default: agy-skill-agent
    SHOW_TOOLS               '0' to hide 🔧 tool calls / ↪ results (default: show)

Requires: `gcloud auth application-default login`.
"""
from __future__ import annotations

import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")  # silence google-genai "experimental" notices

from google.genai import Client  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "rocketech-de-pgcp-sandbox")
LOCATION = os.environ.get("MANAGED_AGENT_LOCATION", "global")
AGENT_ID = os.environ.get("MANAGED_AGENT_ID", "agy-skill-agent")
SHOW_TOOLS = os.environ.get("SHOW_TOOLS", "1").lower() in ("1", "true", "yes")


def _w(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def _clip(value, limit: int = 160) -> str:
    text = " ".join(str(value).split())
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


def _friendly_result(result) -> str:
    """Human-readable description of a tool result (no raw JSON)."""
    if isinstance(result, dict):
        if "Output" in result:                       # run_command
            return _clip(_clean_output(result.get("Output"))) or "(no output)"
        if isinstance(result.get("results"), list):  # list_dir
            names = [r.get("name") for r in result["results"] if isinstance(r, dict) and r.get("name")]
            return "found: " + ", ".join(names) if names else "(empty)"
        if result.get("Status"):                     # create/delete/edit
            return str(result["Status"])
        if "content" in result:                      # view_file
            return "(file read)"
    return _clip(result)


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


def ask(client: Client, prompt: str, state: dict) -> None:
    """Stream one turn live. Carries conversation + sandbox across turns via `state`."""
    kwargs = {
        "agent": AGENT_ID,
        "input": prompt,
        "background": True,   # required for managed agents
        "store": True,
        "stream": True,       # live SSE events
    }
    if state.get("previous_interaction_id"):
        kwargs["previous_interaction_id"] = state["previous_interaction_id"]
    if state.get("environment_id"):
        kwargs["environment"] = {"env_id": state["environment_id"]}

    buffer = ""          # text printed so far in the current step (to drop consolidations)
    wrote_text = False    # did the current step emit any text?
    step_type = None      # type of the current step (model_output / function_call / ...)
    step_name = ""        # tool name for a function_call step
    args_buf = ""         # accumulated arguments JSON for a function_call step

    for ev in client.interactions.create(**kwargs):
        name = type(ev).__name__
        data = ev.model_dump() if hasattr(ev, "model_dump") else {}

        # capture ids for multi-turn continuity (conversation + sandbox)
        inter = data.get("interaction") if isinstance(data.get("interaction"), dict) else {}
        new_id = data.get("id") or inter.get("id")
        if new_id:
            state["previous_interaction_id"] = new_id
        env_id = data.get("environment_id") or inter.get("environment_id")
        if env_id:
            state["environment_id"] = env_id

        if name == "StepStart":
            step = data.get("step") or {}
            step_type, step_name = step.get("type"), step.get("name") or ""
            buffer, wrote_text, args_buf = "", False, ""
        elif name == "StepStop":
            if step_type == "model_output" and wrote_text:
                _w("\n")
            elif step_type == "function_call" and SHOW_TOOLS:
                try:
                    args = json.loads(args_buf) if args_buf else {}
                except json.JSONDecodeError:
                    args = {}
                _w(f"{_friendly_call(step_name, args)}\n")
        elif name == "StepDelta":
            delta = data.get("delta") or {}
            if "text" in delta and delta.get("text") is not None:
                x = delta["text"]
                if not x or x == buffer:
                    continue                      # skip the consolidated repeat
                _w(x[len(buffer):] if x.startswith(buffer) else x)
                buffer = x if x.startswith(buffer) else buffer + x
                wrote_text = True
            elif delta.get("type") == "arguments_delta":
                args_buf += delta.get("arguments") or ""
            elif SHOW_TOOLS and "result" in delta:
                _w(f"   ↳ {_friendly_result(delta.get('result'))}\n")
        elif name == "InteractionCompletedEvent":
            status = str(data.get("status") or inter.get("status") or "").lower()
            if status and status != "completed":
                _w(f"\n[ended with status '{status}']\n")
    _w("\n")


def main() -> int:
    client = Client(vertexai=True, project=PROJECT, location=LOCATION)
    state: dict = {}
    print(f"Connected to managed agent '{AGENT_ID}' ({PROJECT}, {LOCATION}). "
          "Streaming live; skills load from the bucket.")

    if len(sys.argv) > 1:  # one-shot
        prompt = " ".join(sys.argv[1:])
        print(f"\n> {prompt}\n")
        ask(client, prompt, state)
        return 0

    print("Type your message (Ctrl-C or 'exit' to quit; SHOW_TOOLS=0 to hide tool steps).")
    while True:
        try:
            prompt = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return 0
        if prompt.lower() in ("exit", "quit"):
            return 0
        if prompt:
            print()
            ask(client, prompt, state)


if __name__ == "__main__":
    sys.exit(main())
