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

"""after_agent_callback that surfaces the rendered chart inline in the final response.

Gemini Enterprise only renders files returned as inline ``types.Part`` objects in the final
agent response; files merely saved via ``tool_context.save_artifact()`` are not rendered
(adk-python#4273). ADK tools must return ``str``/``dict`` (returning a ``Part`` breaks the
function schema), so ``render_chart`` saves the artifact and stashes a pointer in session
state, and this callback loads it and returns it as an inline image ``Part`` — appended
after the model's headline text (the callback's returned Content is emitted as an extra
event, it does not replace the text).
"""

from __future__ import annotations

from google.genai import types

from app.sandbox.render_tool import PENDING_CHART_KEY


async def attach_chart_to_response(callback_context) -> types.Content | None:
    """Return the just-rendered chart as an inline image Part, or None if there is none.

    Reads the ``PENDING_CHART_KEY`` pointer written by ``render_chart``, consumes it (so it
    is not re-attached on later turns), loads the artifact, and wraps it in a ``Content``.
    """
    pending = callback_context.state.get(PENDING_CHART_KEY)
    if not pending:
        return None

    # Consume the pointer regardless of outcome so a stale flag never re-attaches the image.
    callback_context.state[PENDING_CHART_KEY] = None

    part = await callback_context.load_artifact(pending["filename"], pending["version"])
    if part is None:
        return None

    return types.Content(role="model", parts=[part])
