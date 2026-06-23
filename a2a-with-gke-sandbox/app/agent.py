# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mimetypes
import os
from pathlib import Path

import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.skills import list_skills_in_dir, load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset
from google.genai import types

from app.a2ui_support import (
    MAX_UPLOAD_BYTES,
    URL_MAP_KEY,
    build_a2ui_toolset,
    setup_a2ui_state,
    substitute_a2ui_urls,
)
from app.sandbox.client import SandboxError, run_python
from app.sandbox.session_files import (
    load_session_files,
    persist_uploads,
    session_file_names,
)
from app.sandbox.signed_url import upload_and_sign

# Auto-fix loop: on a sandbox failure, run_code returns the error so the model can rewrite
# and retry (the ADK agent loop re-prompts after each tool result). Capped per turn.
_RUN_CODE_MAX_ATTEMPTS = int(os.environ.get("RUN_CODE_MAX_ATTEMPTS", "3"))

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


def _part_filename(index, blob) -> str:
    return getattr(blob, "display_name", None) or f"upload_{index}"


def _uploaded_files(content) -> list[tuple[str, bytes]]:
    """Return (name, bytes) for each within-cap inline_data file in a user Content.

    Over-cap uploads are rejected upstream in the A2A executor (a2ui_support) before the model
    runs, so they never get here; we skip any that slip through (e.g. a rehydrated file) rather
    than raise, so a single bad file can't crash the run.
    """
    out: list[tuple[str, bytes]] = []
    for i, part in enumerate((content.parts if content else None) or []):
        blob = getattr(part, "inline_data", None)
        data = getattr(blob, "data", None) if blob else None
        if not data or len(data) > MAX_UPLOAD_BYTES:
            continue
        out.append((_part_filename(i, blob), data))
    return out


def run_code(code: str, tool_context) -> str:
    """Run model-written Python in the isolated GKE sandbox; return stdout.

    Files the user uploaded this turn are written into the sandbox first (open them by name).
    Any files the code *writes* (charts, reports) are returned to the user as attachments —
    write a file rather than printing bytes. On failure the error is returned so you can fix
    the code and call run_code again (bounded retries).

    Args:
        code: A self-contained Python script that prints its result and/or writes output files.
    """
    # Files persist across turns of a conversation: stash this turn's uploads, then re-hydrate
    # the whole conversation's set so a follow-up ("now a pie chart") still has the file even
    # though GE only attaches it on the upload turn and the sandbox is fresh per request.
    session_id = getattr(getattr(tool_context, "session", None), "id", None)
    turn_files = _uploaded_files(getattr(tool_context, "user_content", None))
    files = turn_files
    if session_id:
        try:
            persist_uploads(session_id, turn_files)
            files = load_session_files(session_id) or turn_files
        except Exception:  # noqa: BLE001 - GCS hiccup: fall back to this turn's uploads
            files = turn_files
    try:
        result = run_python(
            code,
            api_url=os.environ["SANDBOX_API_URL"],
            template=os.environ["SANDBOX_TEMPLATE"],
            namespace=os.environ["SANDBOX_NAMESPACE"],
            endpoint=os.environ["GKE_ENDPOINT"],
            ca_cert_path=os.environ.get("GKE_CA_CERT_PATH"),
            files=files,
        )
    except SandboxError as exc:
        # No data available + a missing-file error: don't let the model "fix" it by fabricating
        # data — tell it to ask the user to attach the file. (Stops the silent reconstruct path.)
        if not files and "No such file" in str(exc):
            return (
                "ERROR: no data file is available in the sandbox. Do NOT fabricate, hardcode, or "
                "reconstruct the data — ask the user to attach the file, then try again."
            )
        # Return the error (don't raise) so the agent loop re-prompts the model to fix it.
        # Attempts are counted per turn (keyed by invocation_id) so the cap resets each turn.
        key = f"run_code_attempts:{getattr(tool_context, 'invocation_id', '')}"
        attempt = int(tool_context.state.get(key, 0)) + 1
        tool_context.state[key] = attempt
        if attempt < _RUN_CODE_MAX_ATTEMPTS:
            return (
                f"ERROR (attempt {attempt}/{_RUN_CODE_MAX_ATTEMPTS}): {exc}\n"
                "Fix the code and call run_code again."
            )
        return (
            f"ERROR: failed after {_RUN_CODE_MAX_ATTEMPTS} attempts: {exc}. "
            "Report this failure to the user; do not retry."
        )

    # Success: image outputs are hosted + handed back as signed URLs (so the model can render
    # them via an A2UI Image in Gemini Enterprise); other files become A2A attachments.
    saved: list[str] = []
    images: list[tuple[str, str]] = []  # (name, placeholder token)
    for name, data in result.files:
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        if mime.startswith("image/"):
            try:
                url = upload_and_sign(data, name, mime)
                # Hand the model a short placeholder, not the long signed URL — the converter
                # substitutes the real URL after the LLM, so it can't be mangled in transit.
                # Key it by FILENAME: the model reconstructs the token from the filename rather
                # than copying a random one verbatim, so this is what it actually emits.
                token = "{{chart:" + name + "}}"
                url_map = dict(tool_context.state.get(URL_MAP_KEY) or {})
                url_map[token] = url
                tool_context.state[URL_MAP_KEY] = url_map
                images.append((name, token))
                continue
            except Exception:  # noqa: BLE001 - fall back to attachment if hosting fails
                pass
        tool_context.save_artifact(
            name, types.Part(inline_data=types.Blob(data=data, mime_type=mime))
        )
        saved.append(name)

    out = result.stdout
    if images:
        listing = "; ".join(f"{name} -> {token}" for name, token in images)
        out += (
            f"\n\n[Generated image(s): {listing}. To display each, call "
            "send_a2ui_json_to_client with an A2UI Image component whose url is the placeholder "
            'token EXACTLY as written (e.g. "{{chart:...}}") — it resolves to the real image.]'
        )
    if saved:
        out += f"\n\n[Saved attachments: {', '.join(saved)}]"
    return out


# Register all skills under skills/ with only their name+description loaded; the full
# SKILL.md content is fetched on demand at runtime via the toolset's `load_skill` tool
# (progressive disclosure). The toolset also injects the "use the skill tools" instruction.
_SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"
skill_toolset = SkillToolset(
    skills=[
        load_skill_from_dir(_SKILLS_DIR / name)
        for name in list_skills_in_dir(str(_SKILLS_DIR))
    ]
)


def _before_model(callback_context, llm_request):
    """Prep the request before the model call: strip part_metadata, advertise uploads.

    1. Strip Part.part_metadata — Gemini Enterprise sends A2A parts carrying `metadata`,
       which ADK maps onto genai `Part.part_metadata`; the Vertex / GE Agent Platform
       backend rejects it ("only supported in Gemini Developer API mode").
    2. If the latest user turn included uploaded files, tell the model their filenames so
       it opens them by name in run_code (rather than inlining contents) — run_code writes
       those same files into the sandbox working dir before executing.
    """
    last_user = None
    for content in llm_request.contents or []:
        for part in content.parts or []:
            if getattr(part, "part_metadata", None) is not None:
                part.part_metadata = None
        if content.role == "user":
            last_user = content

    names = [name for name, _ in _uploaded_files(last_user)] if last_user else []
    # Also advertise files persisted earlier in this conversation (a follow-up turn carries no
    # attachment, but run_code re-hydrates them) so the model opens the file instead of inventing it.
    session_id = getattr(getattr(callback_context, "session", None), "id", None)
    if session_id:
        try:
            for n in session_file_names(session_id):
                if n not in names:
                    names.append(n)
        except Exception:  # noqa: BLE001 - GCS hiccup: just advertise this turn's uploads
            pass
    if names:
        listed = ", ".join(names)
        llm_request.append_instructions([
            f"The user uploaded these files, already available in your code sandbox's working "
            f"directory: {listed}. When writing Python for run_code, open them directly by "
            f"name (e.g. open({names[0]!r})). Do NOT paste file contents into the code."
        ])
    return None


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    # Emit the model's reasoning as thought summaries (surfaced as thought parts in the
    # A2A stream / traces). Whether a given client renders them is up to the client.
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(include_thoughts=True),
    ),
    description="An agent that solves tasks by writing Python and running it in an isolated GKE sandbox.",
    instruction="You are a helpful AI assistant designed to provide accurate and useful information."
    + "\n\nIf you need more information to answer, ask the user a clarifying question as a"
    + " normal reply and wait for their next message — do not assume missing details.",
    tools=[
        run_code,
        skill_toolset,
        # send_a2ui_json_to_client — lets the agent render rich UI (e.g. a chart Image) in
        # Gemini Enterprise. Only active once the A2UI executor negotiates the catalog.
        build_a2ui_toolset(),
    ],
    before_model_callback=_before_model,
    # Enable A2UI + load the catalog into session state so the send_a2ui_json_to_client tool
    # is exposed and emitted A2UI is converted to application/json+a2ui parts.
    before_agent_callback=setup_a2ui_state,
    # Swap {{chart:...}} placeholders for the real signed URLs while tool-state is still live.
    before_tool_callback=substitute_a2ui_urls,
)

app = App(
    root_agent=root_agent,
    name="app",
)
