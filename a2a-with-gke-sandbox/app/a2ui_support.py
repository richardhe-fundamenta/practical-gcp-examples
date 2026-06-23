"""A2UI (Gemini Enterprise) rich-rendering support.

GE renders rich content only via A2UI — a constrained, validated component catalog — not raw
HTML, and (in testing) not bare image/png file parts. This wires the `a2ui-agent-sdk` so the
agent can emit standard A2UI components (e.g. an Image pointing at a signed URL) that GE
renders inline.

Pieces:
- A schema manager for A2UI **v0.8** (the only version GE supports), over the bundled standard
  component catalog (we only use standard components like Image/Text, so no custom catalog).
- `setup_a2ui_state` — a before_agent_callback that puts the catalog/examples/enabled flag into
  session state. We do this here rather than in a custom executor because `A2aAgentExecutor`
  delegates to an internal impl, so subclass `_prepare_session` overrides are never called.
- `build_a2ui_toolset()` — the `send_a2ui_json_to_client` tool (exposed once state is set).
- `A2uiAgentExecutor` — configures `A2uiEventConverter` (turns emitted A2UI into
  `application/json+a2ui` parts) and keeps the artifact interceptor.
"""
from __future__ import annotations

import builtins
import json
import logging
import os
import uuid

from google.adk import models as _adk_models

logger = logging.getLogger(__name__)

# a2ui-agent-sdk 0.2.x evaluates `models.LlmRequest` annotations at import time without
# importing `models`; expose it as a builtin before importing the toolset module.
if not hasattr(builtins, "models"):
    builtins.models = _adk_models

from datetime import UTC, datetime  # noqa: E402

from a2a.types import (  # noqa: E402
    AgentExtension,
    Artifact,
    Part,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from a2ui.a2a.extension import get_a2ui_agent_extension  # noqa: E402
from a2ui.adk.a2a.part_converter import A2uiPartConverter  # noqa: E402
from a2ui.adk.send_a2ui_to_client_toolset import (  # noqa: E402
    SendA2uiToClientToolset,
)
from a2ui.basic_catalog.provider import BasicCatalog  # noqa: E402
from a2ui.schema.common_modifiers import remove_strict_validation  # noqa: E402
from a2ui.schema.constants import (  # noqa: E402
    A2UI_TOOL_NAME,
    VERSION_0_8,
)
from a2ui.schema.manager import A2uiSchemaManager  # noqa: E402
from google.adk.a2a.converters.event_converter import (  # noqa: E402
    convert_event_to_a2a_events,
)
from google.adk.a2a.converters.utils import _get_adk_metadata_key  # noqa: E402
from google.adk.a2a.executor.a2a_agent_executor import (  # noqa: E402
    A2aAgentExecutor,
    A2aAgentExecutorConfig,
)
from google.adk.a2a.executor.executor_context import ExecutorContext  # noqa: E402
from google.adk.a2a.executor.interceptors import (  # noqa: E402
    include_artifacts_in_a2a_event_interceptor,
)
from google.adk.a2a.executor.task_result_aggregator import (  # noqa: E402
    TaskResultAggregator,
)
from google.adk.a2a.executor.utils import (  # noqa: E402
    execute_after_agent_interceptors,
    execute_after_event_interceptors,
)
from google.adk.platform import time as platform_time  # noqa: E402
from google.adk.platform import uuid as platform_uuid  # noqa: E402
from google.adk.utils.context_utils import Aclosing  # noqa: E402

_ENABLED_KEY = "system:a2ui_enabled"
_CATALOG_KEY = "system:a2ui_catalog"  # must match A2uiEventConverter's default catalog_key
# Maps short placeholder tokens (e.g. "{{chart:ab12}}") -> real signed URLs. run_code writes
# this; the event converter substitutes after the LLM so the model never transcribes the URL.
URL_MAP_KEY = "a2ui_url_map"

# Per-file cap on uploads. Enforced in the executor (_handle_request) *before* the model runs:
# an over-cap inline file must never reach the model or get echoed back, since a multi-MB blob in
# the A2A response makes it oversize and 500s. agent.py imports this for its own skip guard.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _strip_oversized_parts(message) -> list[tuple[str, int]]:
    """Drop over-cap inline file parts from an incoming A2A message, in place.

    Returns [(name, nbytes)] for what was removed. The incoming parts are a2a FileParts with
    base64 `bytes`; an over-cap blob must be removed *before the framework stores the message*,
    because a2a seeds the Task's history with this same object and echoes it in the response — a
    multi-MB blob there blows past Cloud Run's response limit and 500s. Mutating in place (the
    Task history holds the same reference) keeps it out of both the response and the model call.
    """
    removed: list[tuple[str, int]] = []
    kept = []
    for part in getattr(message, "parts", None) or []:
        file = getattr(getattr(part, "root", None), "file", None)
        b64 = getattr(file, "bytes", None) if file else None
        if b64:
            nbytes = (len(b64) * 3) // 4  # approx decoded size of the base64 payload
            if nbytes > MAX_UPLOAD_BYTES:
                removed.append((getattr(file, "name", None) or "upload", nbytes))
                continue
        kept.append(part)
    if removed:
        message.parts = kept
    return removed


# v0.8 schema manager over the bundled standard catalog (Image, Text, Card, ...).
_schema_manager = A2uiSchemaManager(
    version=VERSION_0_8,
    catalogs=[BasicCatalog.get_config(version=VERSION_0_8)],
    accepts_inline_catalogs=True,
    schema_modifiers=[remove_strict_validation],
)

# GE sends no A2UI client capabilities; default to the standard v0.8 catalog. Built once.
_DEFAULT_CATALOG = _schema_manager.get_selected_catalog(client_ui_capabilities=None)

# The bundled catalog ships no examples, which left the model guessing — it sent a
# `beginRendering` with no `surfaceUpdate` (an empty surface → nothing renders). This
# validated example shows the complete shape: ONE call whose a2ui_json is a LIST containing
# BOTH messages. Injected into the system prompt by the toolset.
_A2UI_EXAMPLES = """\
To display a result, make ONE send_a2ui_json_to_client call whose a2ui_json is a JSON LIST
containing BOTH a beginRendering and a surfaceUpdate message. Never send beginRendering alone
(that renders an empty surface). Column children use {"explicitList": [<component ids>]}.
Copy any {{chart:...}} placeholder token EXACTLY — it resolves to the real image.

Lay the surface out top-to-bottom as: a title, a "Thinking" section (2-4 short sentences
explaining how you approached the task and what the data shows — your reasoning, in plain
language), then the chart Image below it.

Example — title, a thinking/approach section, and the chart image:

[
  {"beginRendering": {"surfaceId": "report", "root": "root", "styles": {}}},
  {"surfaceUpdate": {"surfaceId": "report", "components": [
    {"id": "root", "component": {"Column": {"children": {"explicitList": ["title", "thinking", "chart"]}}}},
    {"id": "title", "component": {"Text": {"text": {"literalString": "Daily spend by campaign"}, "usageHint": "h3"}}},
    {"id": "thinking", "component": {"Text": {"text": {"literalString": "I grouped the rows by campaign and summed spend_usd, then sorted ascending. Spend ranges from $800 (Summer) to $1,500 (Fall); Fall is the clear top spender."}}}},
    {"id": "chart", "component": {"Image": {"url": {"literalString": "{{chart:ab12}}"}}}}
  ]}}
]
"""


def a2ui_agent_extension() -> AgentExtension:
    """The A2UI extension to advertise on the agent card."""
    return get_a2ui_agent_extension(
        VERSION_0_8,
        _schema_manager.accepts_inline_catalogs,
        _schema_manager.supported_catalog_ids,
    )


def setup_a2ui_state(callback_context):
    """before_agent_callback: enable A2UI + stash the catalog/examples in session state.

    The toolset reads `_ENABLED_KEY`/`_CATALOG_KEY`/`_EXAMPLES_KEY` to expose its tool, and
    A2uiEventConverter reads `_CATALOG_KEY` to emit application/json+a2ui parts. Return None to
    proceed normally.
    """
    callback_context.state[_ENABLED_KEY] = True
    callback_context.state[_CATALOG_KEY] = _DEFAULT_CATALOG
    return None


def build_a2ui_toolset() -> SendA2uiToClientToolset:
    """The send_a2ui_json_to_client tool; exposed only once setup_a2ui_state set the state."""
    return SendA2uiToClientToolset(
        a2ui_enabled=lambda ctx: ctx.state.get(_ENABLED_KEY, False),
        a2ui_catalog=lambda ctx: ctx.state.get(_CATALOG_KEY),
        a2ui_examples=lambda ctx: _A2UI_EXAMPLES,
    )


def _uniquify_surface_ids(a2ui_json: str) -> str:
    """Suffix every surfaceId with a per-call token so each chart renders as its OWN A2UI surface.

    A2UI keys a render target by surfaceId; the model copies the example's `surfaceId: "report"`
    verbatim on every turn, so Gemini Enterprise updates the SAME surface in place and the new
    chart replaces the previous turn's. Rewriting to a unique id per call makes GE render a new
    card each time and keeps earlier charts. Distinct surfaceIds within one call stay distinct
    (same original -> same new), so beginRendering and surfaceUpdate still match.
    """
    try:
        data = json.loads(a2ui_json)
    except Exception:
        return a2ui_json
    suffix = uuid.uuid4().hex[:8]
    mapping: dict[str, str] = {}

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "surfaceId" and isinstance(v, str):
                    obj[k] = mapping.setdefault(v, f"{v}-{suffix}")
                else:
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return json.dumps(data)


def substitute_a2ui_urls(tool, args, tool_context):
    """before_tool_callback for send_a2ui_json_to_client. Two rewrites of the model's a2ui_json:

    1. Replace `{{chart:...}}` placeholder tokens with the real signed URLs run_code stashed in
       state — so the model never has to copy a long signed URL verbatim. Done here (not in the
       event converter) because tool-execution state is live; the converter's snapshot is not.
    2. Give each call a unique surfaceId so Gemini Enterprise renders a new card per chart instead
       of overwriting the previous turn's (see _uniquify_surface_ids).
    """
    if getattr(tool, "name", None) != A2UI_TOOL_NAME:
        return None
    raw = args.get("a2ui_json")
    if not isinstance(raw, str):
        return None
    for token, url in (tool_context.state.get(URL_MAP_KEY) or {}).items():
        raw = raw.replace(token, url)
    args["a2ui_json"] = _uniquify_surface_ids(raw)
    return None


class _A2uiEventConverter:
    """Event converter that ALWAYS uses the A2UI part converter (v0.8 standard catalog).

    We pin the catalog here instead of reading it from session state (as the stock
    A2uiEventConverter does): the catalog object isn't JSON-serializable, so it's absent from
    the session snapshot at conversion time and the stock converter silently falls back to the
    plain converter — emitting a raw function_response that GE can't render."""

    def __init__(self):
        self._part_convert = A2uiPartConverter(_DEFAULT_CATALOG).convert

    def __call__(
        self, event, invocation_context, task_id=None, context_id=None, part_converter_func=None
    ):
        return convert_event_to_a2a_events(
            event, invocation_context, task_id, context_id, self._part_convert
        )


def _now_iso() -> str:
    return datetime.fromtimestamp(platform_time.get_time(), tz=UTC).isoformat()


class A2uiAgentExecutor(A2aAgentExecutor):
    """A2aAgentExecutor for Gemini Enterprise A2UI rendering.

    Two things GE requires that the stock executor doesn't give us (verified against a working
    reference agent):

    1. `use_legacy=True` — GE sends the "new ADK integration" extension, which otherwise routes
       to an internal impl that bypasses this class entirely (our overrides would be dead code).
    2. The result must land in the COMPLETED task's `artifacts`. GE polls `tasks/get`; while the
       task is `working` it shows `status.message`, and once `completed` it renders
       `task.artifacts` (it does NOT replay history). The stock flow leaves the A2UI in an
       intermediate `working` event and the final `completed` message empty → GE shows nothing.
       So we aggregate the result and re-emit it as a `TaskArtifactUpdateEvent(last_chunk=True)`
       right before the `completed` event.
    """

    def __init__(self, *, runner):
        super().__init__(
            runner=runner,
            config=A2aAgentExecutorConfig(
                event_converter=_A2uiEventConverter(),
                execute_interceptors=[include_artifacts_in_a2a_event_interceptor],
            ),
            use_legacy=True,
        )

    async def _handle_request(self, context, event_queue):
        runner = await self._resolve_runner()

        # Reject over-cap uploads up front — BEFORE building the run request or enqueuing any event
        # (the framework seeds the Task history from this same message object). Strip the blob so it
        # never reaches the model or the response, then emit the "too large" text as the completed
        # task's artifact — the path GE renders — so the user sees a message, not a hung spinner.
        oversized = _strip_oversized_parts(context.message)
        if oversized:
            limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
            listed = ", ".join(f"{n} ({sz / (1024 * 1024):.1f} MB)" for n, sz in oversized)
            text = (
                f"⚠️ That file is too large to process ({listed}). The limit is {limit_mb} MB "
                f"per file — please upload a smaller file and try again."
            )
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    final=False,
                    status=TaskStatus(state=TaskState.working, timestamp=_now_iso()),
                )
            )
            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    last_chunk=True,
                    artifact=Artifact(
                        artifact_id=platform_uuid.new_uuid(),
                        parts=[Part(root=TextPart(text=text))],
                    ),
                )
            )
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    final=True,
                    status=TaskStatus(state=TaskState.completed, timestamp=_now_iso()),
                )
            )
            return

        run_request = self._config.request_converter(context, self._config.a2a_part_converter)
        executor_context = ExecutorContext(
            app_name=runner.app_name,
            user_id=run_request.user_id,
            session_id=run_request.session_id,
            runner=runner,
        )

        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                final=False,
                status=TaskStatus(state=TaskState.working, timestamp=_now_iso()),
                metadata={
                    _get_adk_metadata_key("app_name"): runner.app_name,
                    _get_adk_metadata_key("user_id"): run_request.user_id,
                    _get_adk_metadata_key("session_id"): run_request.session_id,
                },
            )
        )

        # Gemini intermittently returns MALFORMED_FUNCTION_CALL on the (large) final
        # send_a2ui_json_to_client call, which fails the whole task. Retry the run on a FRESH
        # session (so the model doesn't continue from its botched turn) before giving up.
        # We emit the terminal event ourselves below, so suppress any final=True events from a
        # failed attempt — otherwise message/send would return on the first attempt's failure.
        max_attempts = int(os.environ.get("A2UI_RENDER_MAX_ATTEMPTS", "2"))
        aggregator = TaskResultAggregator()
        for attempt in range(max_attempts):
            if attempt > 0:
                run_request.session_id = platform_uuid.new_uuid()
                logger.warning(
                    "A2UI render attempt %d failed (state=%s); retrying on a fresh session",
                    attempt,
                    aggregator.task_state,
                )
            session = await self._prepare_session(context, run_request, runner)
            invocation_context = runner._new_invocation_context(
                session=session,
                new_message=run_request.new_message,
                run_config=run_request.run_config,
            )
            aggregator = TaskResultAggregator()
            async with Aclosing(runner.run_async(**vars(run_request))) as agen:
                async for adk_event in agen:
                    for a2a_event in self._config.event_converter(
                        adk_event,
                        invocation_context,
                        context.task_id,
                        context.context_id,
                        self._config.gen_ai_part_converter,
                    ):
                        a2a_events = await execute_after_event_interceptors(
                            a2a_event,
                            executor_context,
                            adk_event,
                            self._config.execute_interceptors,
                        )
                        for e in a2a_events:
                            aggregator.process_event(e)
                            if getattr(e, "final", False):
                                continue  # we emit the single terminal event below
                            await event_queue.enqueue_event(e)
            if aggregator.task_state != TaskState.failed:
                break

        # Move the result into a final artifact so GE renders it on task completion.
        msg = aggregator.task_status_message
        if aggregator.task_state == TaskState.working and msg is not None and msg.parts:
            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    task_id=context.task_id,
                    context_id=context.context_id,
                    last_chunk=True,
                    artifact=Artifact(
                        artifact_id=platform_uuid.new_uuid(), parts=msg.parts
                    ),
                )
            )
            final_event = TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                final=True,
                status=TaskStatus(state=TaskState.completed, timestamp=_now_iso()),
            )
        else:
            final_event = TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                final=True,
                status=TaskStatus(
                    state=aggregator.task_state, message=msg, timestamp=_now_iso()
                ),
            )

        final_event = await execute_after_agent_interceptors(
            executor_context, final_event, self._config.execute_interceptors
        )
        await event_queue.enqueue_event(final_event)
