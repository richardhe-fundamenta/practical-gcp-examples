# analyst-harness

A **harness + skill** data-analyst agent on Google Cloud. Ask a business/analytics
question; the agent writes BigQuery SQL, validates and runs it through a non-skippable
safety gate, then generates Python chart code that runs in an isolated sandbox and
returns **one** annotated chart (PNG) with the headline finding.

Built with [ADK](https://adk.dev/) via `agents-cli` (`adk_a2a` template), deployed to
**Cloud Run** behind the **A2A protocol**. Model: `gemini-3.1-pro-preview`.

> Status: core loop complete and evaluated. Cloud Run deploy is wired but the sandbox
> lifecycle + dedicated runtime service account are unfinished — see [TODO.md](./TODO.md).

## Architecture

The design separates an immovable **harness** from a swappable **skill**:

| Concern | Owner |
|---|---|
| Agent loop, BigQuery access, SQL dry-run gate, sandbox execution, containment | **Harness** |
| Output contract (chart type, headline, table), available-package guidance | **Skill** |

Rule of thumb: if a buggy or malicious skill (or bad model-generated render code) were
loaded, the harness must still contain it. Containment is structural — the sandbox has
no network and no credentials, and the renderer charts **only** rows the harness stored
from a validated query (the model cannot inject chart data).

### The loop

1. A2A request (question) → Cloud Run harness.
2. **Schema discovery** via the managed remote BigQuery MCP server (read-only tools only:
   `list_dataset_ids`, `list_table_ids`, `get_dataset_info`, `get_table_info`).
3. Agent drafts a read-only SQL `SELECT` and calls `run_validated_sql`.
4. **Harness dry-run gate** (non-skippable): syntactic validity + bytes-scanned under a
   cap + tables restricted to a dataset allowlist. Rejections go back to the model to
   fix (bounded retries). The model can never reach raw `execute_sql`.
5. Validated query runs; rows are stored in session state.
6. Agent generates matplotlib code; `render_chart` ships it + the stored rows
   (`data.json`) into the **Agent Engine code-execution sandbox**, runs it, and saves the
   PNG as an ADK **artifact** (surfaced in the dev playground and over A2A as a FilePart).
7. Agent returns the chart + a grounded one-line headline.

## Project Structure

```
adk-agent-sandbox/
├── app/                          # the harness (Cloud Run, A2A)
│   ├── agent.py                  # root LlmAgent: instruction + tool wiring + grounding
│   ├── config.py                 # env-driven settings (project, region, byte cap, allowlist, sandbox)
│   ├── bigquery/
│   │   ├── mcp_schema.py         # remote BQ MCP toolset — read-only schema discovery
│   │   ├── validation.py         # HARNESS-OWNED dry-run gate (validity + byte cap + allowlist)
│   │   ├── execute.py            # run validated query (byte + row caps)
│   │   └── sql_tool.py           # run_validated_sql — the only execution surface; stores rows
│   ├── sandbox/
│   │   ├── client.py             # Agent Engine code-exec: ship code + data.json, return artifact
│   │   └── render_tool.py        # render_chart — charts ONLY stored validated rows; saves PNG artifact
│   ├── skills/
│   │   ├── registry.py           # discover skills, parse frontmatter, fold references into contract
│   │   └── loader.py             # active skill contract (default: analyst-chart-table)
│   └── fast_api_app.py           # A2A FastAPI server (artifact + session services)
├── skills/
│   └── analyst-chart-table/
│       ├── SKILL.md              # output contract the model renders against
│       └── references/           # output-contract, security-notes, available-packages, example_render
├── bootstrap/
│   ├── create_dataset.py         # creates the analyst_demo BigQuery demo dataset (US)
│   └── create_sandbox.py         # creates an Agent Engine code-exec sandbox (us-central1)
├── deployment/terraform/         # single-project infra (app_sa, IAM, telemetry) — see TODO.md
├── tests/                        # unit + integration tests
│   └── eval/                     # rubric-based evalset + config (analyst.evalset.json)
├── docs/superpowers/             # design spec + implementation plan
└── .agents-cli-spec.md           # project spec (source of truth)
```

## Requirements

- **uv** — Python package manager — [install](https://docs.astral.sh/uv/getting-started/installation/)
- **agents-cli** — `uv tool install google-agents-cli`
- **Google Cloud SDK** — [install](https://cloud.google.com/sdk/docs/install); run `gcloud auth application-default login`

## Setup

### 1. Install dependencies

```bash
agents-cli install
```

### 2. Provision the demo data + sandbox (one-time)

```bash
# Creates the analyst_demo star schema (customers, products, orders, order_items) in US
uv run python bootstrap/create_dataset.py

# Creates a Python code-execution sandbox (us-central1) under an Agent Engine and prints
# SANDBOX_RESOURCE_NAME. Requires an existing reasoningEngine parent — see the script header.
uv run python bootstrap/create_sandbox.py --engine-name <reasoningEngine resource name>
```

> ⚠️ The Agent Engine code-execution sandbox is **us-central1-only**. Only small,
> aggregated, validated JSON crosses into it (no raw rows); BigQuery data stays in its
> own region. Sandboxes also expire (TTL) — see [TODO.md](./TODO.md) for the planned
> per-session lazy get-or-create lifecycle.

### 3. Configure environment

Create `.env` (gitignored) in the project root:

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=True

# BigQuery data access + the harness dry-run gate
BQ_DATA_REGION=US
BQ_DATASET_ALLOWLIST=analyst_demo          # comma-separated; the gate rejects anything else
BQ_MAX_BYTES_BILLED=1073741824             # 1 GiB cap, enforced before execution

# Agent Engine code-exec sandbox (from bootstrap/create_sandbox.py)
SANDBOX_RESOURCE_NAME=projects/.../locations/us-central1/reasoningEngines/.../sandboxEnvironments/...
```

## Quick Start

```bash
agents-cli playground          # local web UI; ask: "Chart monthly completed-order revenue by region from analyst_demo"
agents-cli run "Compare total completed-order revenue by plan tier in analyst_demo"   # one-shot
```

## Commands

| Command | Description |
|---|---|
| `agents-cli install` | Install dependencies (uv sync) |
| `agents-cli playground` | Local dev web UI (auto-reloads) |
| `agents-cli run "<prompt>"` | One-shot prompt (add `-v` for full event JSON) |
| `uv run pytest tests/unit tests/integration` | Run unit + integration tests |
| `agents-cli eval run --evalset tests/eval/evalsets/analyst.evalset.json --config tests/eval/analyst_config.json` | Run the rubric-based evaluation |
| `agents-cli deploy` | Deploy to Cloud Run |

## Evaluation

Agent behavior is validated with rubric-based eval (not pytest, which only checks code).
The evalset exercises the full loop and asserts the harness guarantees: data is retrieved
via the gated `run_validated_sql`, the chart is rendered via the sandbox, only the
allowlisted dataset is queried, and findings are grounded in real query results (no
fabrication).

```bash
agents-cli eval run \
  --evalset tests/eval/evalsets/analyst.evalset.json \
  --config tests/eval/analyst_config.json
```

## Deployment

```bash
gcloud config set project <your-project-id>
agents-cli deploy --update-env-vars "BQ_DATA_REGION=US,BQ_DATASET_ALLOWLIST=analyst_demo,BQ_MAX_BYTES_BILLED=1073741824,SANDBOX_RESOURCE_NAME=<...>"
```

This builds from the `Dockerfile` (which must include `skills/`) and deploys to Cloud Run
with the A2A endpoint at `/a2a/app`. The runtime service account needs BigQuery and
Vertex AI permissions — see [TODO.md](./TODO.md) for the dedicated-SA + Terraform work
that is not yet complete.

To register with Gemini Enterprise after deploy, see `agents-cli publish gemini-enterprise`.

## Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging.

## A2A Protocol

This agent speaks the [A2A Protocol](https://a2a-protocol.org/). Test interoperability
with the [A2A Inspector](https://github.com/a2aproject/a2a-inspector); the agent card is
served at `/a2a/app/.well-known/agent-card.json`.
