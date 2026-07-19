"""A2A Session Viewer — a tiny local GUI over the BigQuery completions view.

Pick a historical session and see, on a timeline, exactly what happened: the user message,
the model's turns/thinking, each tool call (run_code, load_skill, send_a2ui_json_to_client …)
and its response, plus errors like MALFORMED_FUNCTION_CALL — without writing SQL.

Run:  uv run streamlit run app.py        (from this folder)
Auth: gcloud auth application-default login   (needs BigQuery read on the dataset)
"""
from __future__ import annotations

import json
import os
from itertools import groupby

import altair as alt
import pandas as pd
import streamlit as st
from google.cloud import bigquery

st.set_page_config(page_title="A2A Session Viewer", page_icon="🛰️", layout="wide")

# ---- config (sidebar, with env-var defaults) --------------------------------------------
st.sidebar.header("Source")
project = st.sidebar.text_input("Project", os.environ.get("BQ_PROJECT", "rocketech-de-pgcp-sandbox"))
dataset = st.sidebar.text_input("Dataset", os.environ.get("BQ_DATASET", "cloudrun_agent_sandbox_telemetry"))
view = st.sidebar.text_input("View", os.environ.get("BQ_VIEW", "completions_view"))
session_key = st.sidebar.selectbox("Session key", ["conversation_id", "trace", "user_id"], index=0)
days = st.sidebar.slider("Look back (days)", 1, 60, 7)
limit = st.sidebar.number_input("Max sessions", 10, 1000, 100, step=10)
if st.sidebar.button("↻ Refresh data"):
    st.cache_data.clear()

FQ = f"`{project}.{dataset}.{view}`"

# event kind → (icon label, lane order, colour) -------------------------------------------
KIND = {
    "user":          ("👤 user",          0, "#4285F4"),
    "model":         ("🤖 model",         1, "#5f6368"),
    "thought":       ("💭 thinking",      2, "#9334e6"),
    "tool_call":     ("🔧 tool call",     3, "#FBBC04"),
    "tool_response": ("📥 tool response", 4, "#34A853"),
    "error":         ("⚠️ error",         5, "#EA4335"),
    "event":         ("• event",          6, "#bdc1c6"),
}


@st.cache_resource
def _client(p: str) -> bigquery.Client:
    return bigquery.Client(project=p)


def _q(sql: str, params: list) -> list[dict]:
    job = _client(project).query(
        sql, job_config=bigquery.QueryJobConfig(query_parameters=params)
    )
    return [dict(r) for r in job.result()]


@st.cache_data(ttl=120, show_spinner="Loading sessions…")
def list_sessions(project, dataset, view, key, days, limit) -> list[dict]:
    sql = f"""
      SELECT {key} AS session,
             MIN(timestamp) AS started,
             MAX(timestamp) AS ended,
             COUNT(*) AS events,
             COUNT(DISTINCT api_call_id) AS llm_calls,
             ANY_VALUE(agent_name) AS agent,
             LOGICAL_OR(finish_reasons LIKE '%MALFORMED%') AS had_error
      FROM {FQ}
      WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
        AND {key} IS NOT NULL
      GROUP BY session
      ORDER BY started DESC
      LIMIT @limit
    """
    return _q(sql, [
        bigquery.ScalarQueryParameter("days", "INT64", int(days)),
        bigquery.ScalarQueryParameter("limit", "INT64", int(limit)),
    ])


@st.cache_data(ttl=120, show_spinner="Loading session…")
def load_events(project, dataset, view, key, session) -> list[dict]:
    sql = f"""
      SELECT timestamp, role, message_type, part_type, tool_name, tool_args, tool_response,
             content, finish_reasons, usage_input_tokens, usage_output_tokens, span_id, api_call_id
      FROM {FQ}
      WHERE {key} = @s
      ORDER BY timestamp, message_idx, part_idx
    """
    return _q(sql, [bigquery.ScalarQueryParameter("s", "STRING", session)])


def classify(r: dict) -> str:
    pt = (r.get("part_type") or "").lower()
    role = (r.get("role") or "").lower()
    if r.get("finish_reasons") and "MALFORMED" in r["finish_reasons"]:
        return "error"
    if "response" in pt:
        return "tool_response"
    if "call" in pt or pt == "function_call":
        return "tool_call"
    if "thought" in pt:
        return "thought"
    if role == "user":
        return "user"
    if role in ("model", "assistant"):
        return "model"
    return "event"


def pretty(v) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, indent=2, ensure_ascii=False)
    if isinstance(v, str):
        try:
            return json.dumps(json.loads(v), indent=2, ensure_ascii=False)
        except Exception:
            return v
    return str(v)


def summary(r: dict, kind: str) -> str:
    tn = r.get("tool_name")
    if kind in ("tool_call", "tool_response") and tn:
        return f"{KIND[kind][0]} · {tn}"
    text = (r.get("content") or "").strip().replace("\n", " ")
    if text:
        return f"{KIND[kind][0]} · {text[:90]}"
    return KIND[kind][0]


def _sig(r: dict):
    return (
        r.get("role"), r.get("part_type"), r.get("tool_name"), r.get("content") or "",
        json.dumps(r.get("tool_args"), sort_keys=True, default=str),
        json.dumps(r.get("tool_response"), sort_keys=True, default=str),
    )


def linearize(events: list[dict]) -> list[dict]:
    """Collapse the view's replayed context into the real conversation.

    The completions view repeats every prior message as *input context* on each later LLM call,
    so the same message appears many times. Keep each unique message's first occurrence (which is
    its true chronological position) and tag it with the LLM call it belongs to (numbered by first
    appearance). Result: one clean, ordered "what the model actually did" stream.
    """
    call_no: dict = {}
    seen: set = set()
    out: list[dict] = []
    for r in events:
        cid = r.get("api_call_id")
        if cid and cid not in call_no:
            call_no[cid] = len(call_no) + 1
        sig = _sig(r)
        if sig in seen:
            continue
        seen.add(sig)
        r = dict(r)
        r["_call_no"] = call_no.get(cid, 0)
        out.append(r)
    return out


# ---- UI ---------------------------------------------------------------------------------
st.title("🛰️ A2A Session Viewer")
st.caption(f"Source: {project}.{dataset}.{view} — grouped by `{session_key}`")

try:
    sessions = list_sessions(project, dataset, view, session_key, days, limit)
except Exception as e:  # noqa: BLE001 - surface auth/permission errors in the UI
    st.error(f"Query failed: {e}\n\nRun `gcloud auth application-default login` and check BigQuery access.")
    st.stop()

if not sessions:
    st.warning("No sessions found in the look-back window. Widen the range or change the session key.")
    st.stop()


def _label(s: dict) -> str:
    started = s["started"].strftime("%Y-%m-%d %H:%M:%S") if s.get("started") else "?"
    flag = " ⚠️" if s.get("had_error") else ""
    return f"{started} · {s['events']} ev · {s['llm_calls']} calls · {(s.get('agent') or '—')}{flag} · {str(s['session'])[:8]}"


choice = st.selectbox("Session", options=range(len(sessions)), format_func=lambda i: _label(sessions[i]))
sess = sessions[choice]
events = load_events(project, dataset, view, session_key, sess["session"])

# session metadata
start = sess["started"]
dur = (sess["ended"] - sess["started"]).total_seconds() if sess.get("ended") and start else 0
c1, c2, c3, c4 = st.columns(4)
c1.metric("Events", sess["events"])
c2.metric("LLM calls", sess["llm_calls"])
c3.metric("Duration", f"{dur:.1f}s")
c4.metric("Status", "⚠️ error" if sess.get("had_error") else "✓ ok")
st.code(str(sess["session"]), language=None)

raw = st.toggle(
    "Show raw rows (incl. replayed context)",
    value=False,
    help="Off: the real conversation (each message once, grouped by LLM call). "
         "On: every row the view returns, including prior messages replayed as context on each call.",
)
lin = linearize(events)
shown = events if raw else lin

# build a tidy frame for the timeline (from the linearized stream so it isn't inflated by replays)
rows = []
for r in lin:
    kind = classify(r)
    ts = r["timestamp"]
    rel = (ts - start).total_seconds() if start else 0
    rows.append({
        "rel": round(rel, 2),
        "time": ts.strftime("%H:%M:%S"),
        "call": r.get("_call_no", 0),
        "kind": kind,
        "lane": KIND[kind][0],
        "summary": summary(r, kind),
    })
df = pd.DataFrame(rows)

# ---- timeline chart ----
st.subheader("Timeline")
if not df.empty:
    lane_order = [KIND[k][0] for k in sorted(KIND, key=lambda k: KIND[k][1])]
    colour = alt.Color("lane:N", scale=alt.Scale(
        domain=lane_order, range=[KIND[k][2] for k in sorted(KIND, key=lambda k: KIND[k][1])]),
        legend=alt.Legend(title="Event"))
    chart = (
        alt.Chart(df).mark_circle(size=160, opacity=0.85)
        .encode(
            x=alt.X("rel:Q", title="seconds since start"),
            y=alt.Y("lane:N", sort=lane_order, title=None),
            color=colour,
            tooltip=["time", "rel", "call", "lane", "summary"],
        )
        .properties(height=240)
    )
    st.altair_chart(chart, use_container_width=True)


def render_event(r: dict):
    kind = classify(r)
    rel = (r["timestamp"] - start).total_seconds() if start else 0
    # in→ = fed into the model (context/result); →out = the model's own output (its action)
    io = "→out" if (r.get("message_type") == "output") else "in→"
    with st.expander(f"{io}  +{rel:7.2f}s   {summary(r, kind)}"):
        meta = {k: r.get(k) for k in ("role", "message_type", "part_type", "tool_name",
                                      "finish_reasons", "usage_input_tokens", "usage_output_tokens")
                if r.get(k)}
        st.caption(" · ".join(f"{k}={v}" for k, v in meta.items()))
        if r.get("content"):
            st.markdown("**content**")
            st.code(r["content"], language=None)
        if r.get("tool_args"):
            st.markdown("**tool_args**")
            st.code(pretty(r["tool_args"]), language="json")
        if r.get("tool_response"):
            st.markdown("**tool_response**")
            st.code(pretty(r["tool_response"]), language="json")


# ---- conversation, grouped by LLM call ----
if raw:
    st.subheader(f"Raw rows ({len(events)})")
    for r in events:
        render_event(r)
else:
    st.subheader("Conversation (by LLM call)")
    for call_no, grp in groupby(shown, key=lambda r: r.get("_call_no", 0)):
        grp = list(grp)
        out_row = next((r for r in grp if r.get("message_type") == "output"), grp[-1])
        tin, tout = out_row.get("usage_input_tokens"), out_row.get("usage_output_tokens")
        rel = (grp[0]["timestamp"] - start).total_seconds() if start else 0
        label = f"● LLM call {call_no}" if call_no else "● (context)"
        st.markdown(f"**{label}**  ·  +{rel:.1f}s  ·  in {tin} / out {tout} tok")
        for r in grp:
            render_event(r)
