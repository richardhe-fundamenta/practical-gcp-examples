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

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

import os
import google.auth

from .managed_agent import run_skill_task

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a thin front door to a skills-powered backend. You have NO "
        "capabilities or skills of your own — every capability comes from the "
        "managed skills backend, which you reach ONLY by calling run_skill_task. "
        "The available skills are whatever is currently mounted in that backend; "
        "you do not know them in advance and must never invent, assume, or "
        "describe capabilities from your own knowledge.\n\n"
        "Rules:\n"
        "1. If the user asks what you can do, what skills/capabilities/tools are "
        "available, or anything about your abilities, call run_skill_task with an "
        "instruction like: 'List the skills currently available to you under "
        "/.agent/skills. For each, give its name and a one-line description.' Then "
        "relay exactly what comes back — do not add capabilities it did not list.\n"
        "2. For any actual task, call run_skill_task with a clear, self-contained "
        "instruction and relay the result. If the result includes a section titled "
        "'how the skills agent worked it out', present that step-by-step trace to "
        "the user (e.g. under a 'Behind the scenes' heading) after the answer, so "
        "they can see the reasoning and tool calls — do not hide it.\n"
        "3. Only respond directly (without the tool) for trivial conversational "
        "pleasantries (e.g. 'hello', 'thanks').\n"
        "4. If run_skill_task reports the skills environment is unavailable or not "
        "provisioned, tell the user plainly and do not retry in a loop."
    ),
    tools=[run_skill_task],
)

app = App(
    root_agent=root_agent,
    name="app",
)
