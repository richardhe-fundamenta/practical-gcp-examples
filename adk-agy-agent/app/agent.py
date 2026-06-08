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

import os
from collections.abc import AsyncIterator

import google.auth
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.apps import App
from google.adk.events import Event
from google.genai import types

from .managed_agent import stream_skill_task

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id


def _latest_user_text(ctx: InvocationContext) -> str:
    content = ctx.user_content
    if content and content.parts:
        return "".join(p.text or "" for p in content.parts).strip()
    return ""


class SkillProxyAgent(BaseAgent):
    """Thin pass-through to the managed skills agent.

    No LLM of its own: it forwards the user's message to the managed agent and
    streams that output straight back (reasoning, tool calls, results, answer) in
    order — so there's no second LLM pass on the ADK side. Conversation + sandbox
    continuity is carried in session state.
    """

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncIterator[Event]:
        prompt = _latest_user_text(ctx)
        if not prompt:
            return
        # Emit each chunk as an incremental partial — and DON'T follow with an
        # accumulated final event. With the partial-aware A2A converter
        # (force_new_version in fast_api_app), partial events become append=True
        # artifact deltas; a non-partial final would become an append=False
        # full-text *replace*. Consumers that honor append=False dedupe it, but
        # render-all ones (Gemini Enterprise console) re-render it → the whole
        # answer shown twice. Streaming deltas only means the full text is never
        # re-sent, so it renders exactly once everywhere.
        async for chunk in stream_skill_task(prompt, ctx.session.state):
            if not chunk:
                continue
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=chunk)]),
                partial=True,
            )


root_agent = SkillProxyAgent(
    name="root_agent",
    description="Front door that streams a skills-powered sandbox agent (Skill Registry).",
)

app = App(
    root_agent=root_agent,
    name="app",
)
