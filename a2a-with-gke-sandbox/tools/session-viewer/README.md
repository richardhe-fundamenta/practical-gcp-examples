# A2A Session Viewer

A tiny **local GUI** over the BigQuery completions view so you can understand a run without
writing SQL. Pick a historical session and see, on a **timeline**, exactly what happened:

- the user message,
- the model's turns and **thinking**,
- every **tool call** (`run_code`, `load_skill`, `send_a2ui_json_to_client`, …) and its response,
- errors (e.g. `MALFORMED_FUNCTION_CALL`),

with each event expandable to show the full `content` / `tool_args` / `tool_response`.

## Run

```bash
gcloud auth application-default login        # one-time; needs BigQuery read on the dataset
cd tools/session-viewer
uv run streamlit run app.py                  # opens http://localhost:8501
```

## Configure

Defaults point at this project's telemetry. Override in the sidebar, or via env vars:

```bash
export BQ_PROJECT=rocketech-de-pgcp-sandbox
export BQ_DATASET=a2a_with_gke_sandbox_telemetry
export BQ_VIEW=completions_view
```

The sidebar also lets you choose the **session key** (`conversation_id` — the default — or
`trace` / `user_id`), the look-back window, and how many sessions to list. Hit **↻ Refresh data**
to clear the cache and re-query.

## What you see

- **Session picker** — most recent first, labelled with start time, event/LLM-call counts, agent,
  and a ⚠️ if the run hit a malformed-call error.
- **Metrics** — events, LLM calls, duration, status.
- **Timeline chart** — every event plotted on *seconds-since-start*, laned and colour-coded by
  kind (user / model / thinking / tool call / tool response / error).
- **Conversation (by LLM call)** — the real, de-duplicated sequence of what the model actually
  did, grouped under each **LLM call** (with its input/output token counts). The completions view
  replays every prior message as *input context* on each later call, so the same message appears
  many times; this collapses that to each message's first occurrence. Each event is labelled
  `→out` (the model's own output / action) or `in→` (context or a tool result fed into the call),
  and expands to the raw content + pretty-printed tool args/response.
- **Show raw rows** toggle — flip it to see every row the view returns, including the replayed
  context, if you need the unprocessed data.

It's read-only: it only runs `SELECT`s against the view.
