# Agent Spec — Analyst Harness (chart + table over BigQuery)

> Status: approved design, v1 = **core loop only** (PNG output; no HTML/iframe path,
> no visual-critic loop). Brainstorming copy: `docs/superpowers/specs/2026-05-31-analyst-harness-design.md`.

## Overview

A **harness + skill** data-analyst agent. A user asks a business/analytics question;
the agent writes BigQuery SQL, validates and runs it, aggregates the result *small*
inside BigQuery, and then — guided by a swappable **skill** — **generates Python
rendering code** that the harness runs inside an isolated sandbox to produce **one**
annotated chart + a compact exact-numbers table as a secure PNG.

The design separates an immovable **harness** from swappable **skills**:

| Concern | Owner |
|---|---|
| Which skill loads; the **output contract** (chart type, headline, table, "so what"); the **available-package reference** the model renders against | **Skill** |
| Agent loop, BigQuery access, SQL dry-run validation gate, sandbox provisioning + flags, executing model-generated code, containment | **Harness** |

Rule of thumb: if a buggy or malicious skill (or a bad model-generated render script)
were loaded, the harness must still contain it. A skill/model may produce a bad chart;
it can never weaken containment — containment is the **sandbox isolation**, not the
fixedness of the code.

### Model generates the render code (not a fixed script)

The skill does **not** ship a fixed `render.py`. Instead it specifies *what good output
looks like* (the output contract) and *what libraries are available* in the sandbox. The
model generates the actual Python rendering code each time, targeting the validated,
aggregated data. The harness ships that generated code + the data into the sandbox, runs
it, and returns the artifact. (`render.py` from the original design is kept only as a
**style reference** the skill points the model at — never executed as-is.)

### Two deployables + a skills folder

1. **Harness agent** — ADK `adk_a2a` project, deployed to **Cloud Run**, exposed via
   the **A2A protocol**. Owns the loop, BigQuery access, the dry-run gate, sandbox
   orchestration, and containment.
2. **Agent Runtime Code Execution sandbox** — created **separately** (its own script),
   `us-central1`, Python. **No network access** (egress containment is inherent to the
   sandbox) and a limited filesystem; harness passes **no production credentials** into
   executed code. Session state persists (TTL configurable, up to 14 days) so the
   environment loads once across a skill's steps. File I/O ≤ 100 MB per request/response.
3. **Skills folder** — discovered at startup with progressive disclosure (name +
   description eager; full `SKILL.md` only on activation). Ships the `analyst-chart-table`
   skill: its `SKILL.md` (output contract), `references/` (output-contract, security-notes,
   **available-packages**), and `references/example_render.py` (style reference only).

## Example Use Cases

- **Input:** "Show me net revenue retention by region over the last 12 months."
  **Output:** one line chart titled with the headline finding (e.g. "APAC NRR fell 6%
  vs prior period"), a compact table of exact monthly values, and a one-line "so what".
  Delivered as a single PNG over A2A.
- **Input:** "Compare signups by plan tier this quarter."
  **Output:** one grouped bar chart, headline = the standout tier, exact-numbers table,
  "so what" line. Single PNG.

## Tools Required

- **BigQuery schema discovery** — the fully managed **remote BigQuery MCP server**
  (`https://bigquery.googleapis.com/mcp`, OAuth/IAM, Streamable HTTP). Used **only** for
  read-only schema grounding: `list_dataset_ids`, `list_table_ids`, `get_dataset_info`,
  `get_table_info`. The model never gets `execute_sql` through this path.
- **Harness BigQuery client tool** (`app/bigquery/validation.py` + `execute.py`) —
  the harness-owned, **non-skippable** path that:
  1. **Dry-run validates** drafted SQL via `jobs.query` dryRun: syntactic validity,
     bytes-scanned under a configured cap, and tables restricted to a dataset allowlist.
     Invalid → structured error back to the SQL writer (bounded retries, ~2).
  2. Executes the validated query and aggregates *small* → `data.json`.
- **Agent Runtime sandbox client** (`app/sandbox/client.py`) — ships the **model-generated
  render code** + `data.json` into the code-exec sandbox, runs it, returns artifact bytes.
  Output treated as untrusted.

## Constraints & Safety Rules

- **Dry-run gate is harness-owned and non-skippable.** The model cannot reach `execute_sql`
  directly; all execution goes through the harness validate-then-run path. The model never
  receives credentials or raw row-level data — only validated, pre-aggregated JSON.
- **Byte cap + dataset allowlist** enforced before any execution.
- **Sandbox containment** is structural, not code-dependent: the sandbox has **no network
  access** and a limited filesystem, and the harness passes no production credentials into
  executed code. This holds whether the render code came from a skill or the model. The
  sandbox output file is untrusted regardless of origin.
- **Output contract:** exactly one visual per question — one chart + one compact table +
  one "so what" line. Title states the finding as a conclusion, not a label. Deltas shown,
  not just levels. Adding panels is a contract violation. **Default format = PNG.**
- **Render against available packages only:** the skill provides the sandbox's preinstalled
  library list (e.g. matplotlib 3.10.1, seaborn 0.13.2, plotly 6.1.2, bokeh 3.8.2,
  pandas 2.2.3, numpy 2.1.3, pillow 11.1.0); generated code must not `pip install` or
  assume network access.
- **Residency tradeoff (documented):** Agent Runtime Code Execution is `us-central1`-only.
  Only small, aggregated, validated JSON (no raw rows) ever crosses into the sandbox; the
  BigQuery data itself stays in its own region. If strict residency is later required even
  for aggregates, the sandbox choice must be revisited.
- **Out of scope for v1:** HTML output + iframe/CSP display containment; visual-critic
  screenshot loop. Both are in the broader design but deferred.

## Loop (data flow)

1. A2A request (question) → Cloud Run harness.
2. SQL writer drafts parameterized BigQuery SQL, grounded by the MCP schema tools.
3. Harness **dry-run gate**: validity + bytes under cap + dataset allowlist. Invalid →
   structured error back to writer (bounded retry). The model cannot bypass this path.
4. Execute validated query; aggregate small in BQ → build `data.json`
   (`question / x / series / table / prior`).
5. Skill `analyst-chart-table` activates; its output contract + available-packages list
   are injected. The model **generates Python rendering code** for the validated data.
6. Sandbox client ships the generated code + `data.json` into the sandbox, runs it,
   returns the PNG bytes.
7. Harness returns the PNG as an A2A artifact.

## Module layout

```
adk-agent-sandbox/                # (scaffolded adk_a2a project)
├── app/                          # the harness (Cloud Run, A2A)
│   ├── agent.py                  # root orchestrator (LlmAgent) + wiring
│   ├── bigquery/
│   │   ├── mcp_schema.py         # remote BQ MCP toolset — schema discovery ONLY
│   │   ├── validation.py         # HARNESS-OWNED dry-run gate (validity + byte cap + allowlist)
│   │   └── execute.py            # run validated query, aggregate small → data.json
│   ├── sandbox/
│   │   └── client.py             # Agent Runtime code-exec: ship generated code + data, exec, fetch artifact
│   ├── skills/
│   │   ├── registry.py           # discover folder; name+desc eager; full SKILL.md on activation
│   │   └── loader.py             # inject output contract + available-packages into the render step
│   └── config.py                 # project, data-region, sandbox-region, byte cap, dataset allowlist
├── skills/
│   └── analyst-chart-table/
│       ├── SKILL.md              # output contract (model renders against this)
│       └── references/
│           ├── output-contract.md
│           ├── security-notes.md
│           ├── available-packages.md   # sandbox preinstalled libs (from code-execution overview)
│           └── example_render.py       # style reference only — NOT executed as-is
├── deployment/
│   └── sandbox/create_sandbox.py # creates the Agent Runtime code-exec sandbox (separate step)
└── tests/ + eval/
```

## Success Criteria

- **Eval (primary):** an evalset of representative questions where the tool trajectory is
  writer → validate → execute → render, the dry-run gate is always exercised before
  execution, and the returned artifact is a single PNG honoring the output contract.
- A query that exceeds the byte cap or touches a non-allowlisted dataset is rejected before
  execution.
- Model-generated render code that attempts `pip install` / network access fails in the
  sandbox (no network) and the harness surfaces a clean error — not a corrupt artifact.
- Unit tests pass for: validation gate (valid / invalid / over-cap), `data.json` shaping,
  skill discovery / contract injection, sandbox client (mocked).

## Reference Inputs (from the original zip spec)

- `HARNESS_SPEC.md` — division of responsibility + the loop + containment requirements.
- `SKILL.md`, `output-contract.md`, `security-notes.md` — the analyst-chart-table contract.
- `render.py` — kept as `references/example_render.py` (style reference for the model only).
- Code Execution overview — source of the available-packages list and sandbox limits.
