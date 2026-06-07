# adk-agy-agent

An [ADK](https://adk.dev/) agent that delegates work to a **managed agent**
(Gemini Enterprise Agent Platform) whose **skills are mounted dynamically from a
GCS bucket**. Drop a skill into the bucket and it is usable on the next request —
no redeploy, no sync service.

---

## Architecture

> 📊 **Slide deck for demos:** [`docs/concept.html`](docs/concept.html) — a
> reveal.js walkthrough (why → sandbox execution → scale → Managed Agent API →
> architecture → demo → limitations). Open it locally (`open docs/concept.html`) or
> via [htmlpreview](https://htmlpreview.github.io/) / GitHub Pages — GitHub won't
> render HTML inline.

```
                 ┌──────────────────────────────────────────────────────────┐
   user ───────► │  ADK agent  (app/, A2A server on Cloud Run)              │
                 │  • thin front door — has NO skills of its own            │
                 │  • run_skill_task tool  ──────────────┐                  │
                 └───────────────────────────────────────┼──────────────────┘
                                                          │ Interactions API
                                                          │ POST /interactions
                                                          │ {input, agent,
                                                          │  background:true}
                                                          │ → poll until done
                                                          ▼
                 ┌──────────────────────────────────────────────────────────┐
                 │  Managed agent  (Antigravity sandbox, location=global)    │
                 │  base_environment.sources = [ gs://BUCKET → /.agent ]     │
                 │  • reasons, runs code, reads/writes files in a sandbox    │
                 │  • auto-discovers skills under /.agent/skills/            │
                 └───────────────────────────────────────┬──────────────────┘
                                                          │ loads on demand
                                                          ▼
                 gs://<project>-agy-skills/skills/<name>/SKILL.md (+ files)
                          ▲
                          │  users upload skills here (no redeploy needed)
```

**Two agents, clear split:**

- **ADK agent** (`app/`) — the front door. Built, evaluated, and deployed with
  `agents-cli`. It owns no capabilities; it forwards work to the managed agent via
  a single tool (`run_skill_task`) and relays the result (with an optional
  step-by-step trace of what the managed agent did).
- **Managed agent** — an Antigravity-based agent running in a managed sandbox. It
  mounts the **entire skills bucket** at `/.agent` and discovers skills under
  `/.agent/skills/`. Created **once** by a bootstrap script; never redeployed for
  skill changes.

### Key design decisions

- **Dynamic skills, no sync service.** The sandbox loads skills from GCS *on demand
  per interaction*, so mounting the whole bucket once means new skills appear
  automatically. There is **no** Cloud Run / Eventarc / reconcile layer.
- **One-off bootstrap.** The managed agent is created/patched once
  (`tools/bootstrap_managed_agent.py`), via Terraform or manually.
- **Background + poll.** Managed-agent interactions require `background=true`, so
  the tool creates an interaction and polls it to completion.
- **Session continuity.** Within an ADK session the tool chains conversation
  (`previous_interaction_id`) and reuses the same sandbox (`environment.env_id`),
  so files/state persist across turns.
- **Graceful degradation.** If the managed agent isn't provisioned, or
  credentials/permissions fail, the tool returns a clear message and never crashes.

---

## Code breakdown

```
adk-agy-agent/
├── app/                          # ADK agent (the front door)
│   ├── agent.py                  # root_agent: instruction + run_skill_task tool wiring
│   ├── managed_agent.py          # run_skill_task: create interaction, poll, extract
│   │                             #   answer + step trace; graceful error handling
│   ├── platform_api.py           # REST URL helpers (global host: agents, interactions)
│   ├── config.py                 # env-driven config (project, agent id, timeouts, flags)
│   ├── fast_api_app.py           # A2A FastAPI server — Cloud Run entrypoint (scaffolded)
│   └── app_utils/                # telemetry + typing helpers (scaffolded)
│
├── Dockerfile                    # Cloud Run container image (scaffolded)
│
├── tools/
│   └── bootstrap_managed_agent.py  # one-off idempotent create/patch of the managed
│                                   #   agent with the whole-bucket mount
│
├── examples/
│   └── chat_with_agent.py        # standalone CLI: chat directly with the managed
│                                 #   agent via the Interactions API (uv inline-deps)
│
├── deployment/terraform/
│   ├── single-project/           # single-project infra (manual deploy)
│   │   ├── skills.tf             # ← skills bucket + Agent Platform IAM + bootstrap (local-exec)
│   │   ├── service.tf            # Cloud Run service (app_sa, APP_URL); image updated by deploy
│   │   └── *.tf                  # scaffolded: APIs, telemetry, IAM, storage
│   └── shared/                   # BigQuery telemetry schema + completions SQL (used by telemetry.tf)
│
├── tests/
│   ├── unit/                     # test_managed_agent.py, test_bootstrap.py (mocked, fast)
│   ├── integration/              # scaffolded agent / runtime-app tests
│   └── eval/                     # agents-cli evalsets (basic.evalset.json)
│
├── agents-cli-manifest.yaml      # agents-cli project manifest
├── pyproject.toml                # uv project + dependencies
└── CLAUDE.md                     # AI-assisted development guide
```

### The request flow (`app/managed_agent.py`)

1. **Preflight** `GET agents/{id}` — if missing → "not provisioned" message.
2. **Create** `POST interactions` `{input, agent, background:true, store:true}`
   (+ `previous_interaction_id` and `environment.env_id` for continuity).
3. **Poll** `GET interactions/{id}` until status is terminal (lowercase).
4. **Return** the answer; with `MANAGED_AGENT_SHOW_STEPS=1` (default), a
   de-duplicated chronological trace (💭 reasoning, 🔧 tool call, ↪ result).

---

## Configuration

Set via environment (sensible defaults in `app/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | `rocketech-de-pgcp-sandbox` | GCP project |
| `MANAGED_AGENT_LOCATION` | `global` | Agents/Interactions API location (**must be `global`**) |
| `MANAGED_AGENT_ID` | `agy-skill-agent` | Fixed managed-agent ID |
| `SKILLS_BUCKET` | `<project>-agy-skills` | Skills bucket (bootstrap/infra) |
| `INTERACT_TIMEOUT_S` | `300` | Max time to poll an interaction |
| `INTERACT_POLL_INTERVAL_S` | `3` | Poll interval |
| `MANAGED_AGENT_SHOW_STEPS` | `1` | Include the managed agent's step trace in the reply |
| `MANAGED_AGENT_NETWORK_ALLOWLIST` | `*` | Sandbox egress allowlist (bootstrap) |

---

## Requirements

- **uv** — Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **agents-cli** — `uv tool install google-agents-cli`
- **Google Cloud SDK** — `gcloud` ([install](https://cloud.google.com/sdk/docs/install))
- **Terraform** — for infrastructure ([install](https://developer.hashicorp.com/terraform/downloads))
- Authenticate: `gcloud auth application-default login`

---

## How to run (local)

```bash
agents-cli install                       # uv sync
agents-cli playground                    # web playground at http://127.0.0.1:8000/dev-ui/?app=app
# or a one-shot prompt:
agents-cli run "What are the prime factors of 84?"
```

The local agent calls the **live** managed agent, so the managed agent must exist
(see Deploy → bootstrap) and skills must be in the bucket.

Tests and quality:

```bash
uv run pytest tests/unit tests/integration   # fast, mocked tests
agents-cli lint                              # ruff
agents-cli eval run                          # behavioural eval (tests/eval)
```

### Talk to the managed agent directly (`examples/`)

`examples/chat_with_agent.py` is a standalone client that calls the managed agent
straight through the Interactions API (no ADK layer) and **streams the response
live** — you watch reasoning tokens, tool calls, and tool results arrive in real
time. It's a self-contained `uv` script — the inline metadata pulls a newer
`google-genai` without touching the project's pinned version.

```bash
uv run examples/chat_with_agent.py                       # interactive REPL (streaming)
uv run examples/chat_with_agent.py "prime factors of 90" # one-shot (streaming)
SHOW_TOOLS=0 uv run examples/chat_with_agent.py          # stream text only, hide ↪ tool results
```

Uses `create(..., background=True, stream=True)` and renders SSE deltas as they
arrive. It keeps conversation + sandbox continuity across turns
(`previous_interaction_id` + `environment.env_id`). Targets `MANAGED_AGENT_ID` /
`GOOGLE_CLOUD_PROJECT` (same env vars as above); requires
`gcloud auth application-default login`.

> Note: this **live streaming** is only available when calling the Interactions
> API directly (as here). The ADK `run_skill_task` tool can't stream mid-call, so
> through the ADK agent you get the result (with an after-the-fact step trace) in
> one shot.

---

## Adding skills

Skills are **not** in this repo — upload them to the bucket. A skill is a folder
with a `SKILL.md` (YAML frontmatter + instructions) and optional helper files:

```
skills/<name>/SKILL.md
skills/<name>/scripts/...        # optional
```

```bash
gcloud storage cp -r my-skill gs://<project>-agy-skills/skills/my-skill/
```

It is available on the **next** interaction — no redeploy, no agent update.
(Delete the folder to remove the skill.)

---

## How to deploy

```bash
gcloud config set project <your-project-id>
```

### 1. Provision infra + bootstrap the managed agent

```bash
cd deployment/terraform/single-project
terraform init
# If the skills bucket already exists, import it first:
#   terraform import google_storage_bucket.skills <project>-agy-skills
terraform apply
```

`skills.tf` creates the skills bucket, grants the Agent Platform service identity
read access, and runs `tools/bootstrap_managed_agent.py` once (via `local-exec`) to
create the managed agent with the whole-bucket mount.

> Bootstrap manually instead (idempotent):
> ```bash
> GOOGLE_CLOUD_PROJECT=<id> SKILLS_BUCKET=<project>-agy-skills \
>   uv run python tools/bootstrap_managed_agent.py
> ```

### 2. Deploy the ADK agent (A2A on Cloud Run)

```bash
agents-cli deploy            # builds the container and deploys to Cloud Run
```

The agent is served as an **A2A** service. Its agent card is at
`https://<cloud-run-url>/a2a/app/.well-known/agent-card.json`, and the A2A RPC
endpoint is `https://<cloud-run-url>/a2a/app`. The Cloud Run service account has
`roles/aiplatform.user` (to call the Interactions API) and `roles/storage.admin`.

> Why Cloud Run + A2A (not Agent Runtime): A2A derives the ADK session id from the
> A2A `context_id` (a UUID), so it sidesteps the Agent-Runtime-via-Gemini-Enterprise
> `Invalid session_id` error. (A2A is gated to **ADK 1.x** — see the ADK pin in
> `pyproject.toml`.)

> Manual deploy only — the automated CI/CD scaffolding (`deployment/terraform/cicd/`
> and `.cloudbuild/`) was removed. To add it back: `agents-cli scaffold enhance .
> --cicd-runner google_cloud_build`.

---

## Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging
(`app/app_utils/telemetry.py`, `deployment/terraform/**/telemetry.tf`).

---

## Appendix — verified Managed Agents API contract

Verified live against `aiplatform.googleapis.com` v1beta1. Useful if you change
`app/managed_agent.py`, `app/platform_api.py`, or the bootstrap.

- **Host/location:** global only — `https://aiplatform.googleapis.com/v1beta1`,
  `locations/global`. Regional hosts return "AgentService not supported".
- **Create agent:** `POST .../agents`, ID in the body field `id` (no `agentId`
  query param). Returns an LRO that completes in seconds.
- **Agent body:** `base_agent: "antigravity-preview-05-2026"`;
  `base_environment: {type:"remote", sources:[{type:"GCS", source:"gs://BUCKET",
  target:"/.agent"}], network:{allowlist:[{domain:"*"}]}}`. The `network` block is
  required for create to settle; source `type` is the uppercase enum `GCS`.
- **Patch:** one field per call — a combined update mask 400s, and `tools` is not
  patchable (set only at create).
- **Interactions:** `POST .../interactions` `{input, agent, background:true,
  store:true}` (**`background:true` required** for managed agents). Poll
  `GET .../interactions/{id}`; **status is lowercase**
  (`in_progress|completed|failed|...`).
- **Continuity:** new interaction id per turn (chain via top-level
  `previous_interaction_id`); reuse the sandbox via `environment: {"env_id": ...}`.
- **Response:** answer is in `outputs[]` (a flat list; `text` items hold a
  plain-string `text`, interleaved with `function_call`/`function_result`). It
  contains streaming partials, so de-duplicate (drop a block contained in a later
  one). Tell the agent (system instruction) to state the actual result or it may
  reply with only a summary of steps.
```
