# adk-agy-agent

An [ADK](https://adk.dev/) agent that delegates work to a **managed agent**
(Gemini Enterprise Agent Platform) whose **skills come from the Skill Registry** —
registered from the repo `skills/` folder and mounted **read-only** into the
agent's sandbox. Skills are managed, versioned resources, so they can't be modified
or deleted at runtime. Add a skill = register it + reconcile the agent (one
command), no Cloud Run redeploy.

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
                 │  • thin proxy — NO LLM, no skills of its own             │
                 │  • streams the managed agent straight back ──┐          │
                 └──────────────────────────────────────────────┼─────────┘
                                                          │ Interactions API
                                                          │ POST /interactions
                                                          │ {input, agent,
                                                          │  background:true,
                                                          │  stream:true}  (SSE)
                                                          ▼
                 ┌──────────────────────────────────────────────────────────┐
                 │  Managed agent  (Antigravity sandbox, location=global)    │
                 │  base_environment.sources = [ SKILL_REGISTRY skill        │
                 │                               → /.agent/skills/<id> ]     │
                 │  • reasons, runs code, reads/writes files in a sandbox    │
                 │  • mounts each registered skill (read-only)               │
                 └───────────────────────────────────────┬──────────────────┘
                                                          │ provisioned read-only
                                                          ▼
                 Skill Registry (us-central1):  skills/<id>
                          ▲
                          │  registered from the repo skills/ folder
```

**Two agents, clear split:**

- **ADK agent** (`app/`) — the front door, a thin **streaming proxy** with **no LLM
  of its own** (`SkillProxyAgent`). Built, evaluated, and deployed with `agents-cli`.
  It forwards the user's message to the managed agent and **streams that output
  straight back through A2A**, in order (reasoning → answer) — so there's no second
  LLM pass on the ADK side.
- **Managed agent** — an Antigravity-based agent running in a managed sandbox. It
  mounts each **Skill Registry** skill **read-only** under `/.agent/skills/<id>`.
  Created/patched by a bootstrap script.

### Key design decisions

- **Skills in the Skill Registry.** Skills are managed, versioned resources
  (regional, `us-central1`), mounted read-only — a user chatting with the agent
  can't modify or delete them. The repo `skills/` folder is the source of truth.
- **Register + reconcile.** `tools/register_skills.py` pushes `skills/` to the
  registry; `tools/bootstrap_managed_agent.py` reconciles the agent's
  `base_environment.sources` (one `SKILL_REGISTRY` entry per skill). Run both when
  skills change (Terraform `local-exec` does this).
- **Streaming pass-through (one LLM total).** The ADK agent has no LLM; it streams
  the managed agent's SSE output (`background=true, stream=true`) straight to the
  caller — no re-summarisation pass, so latency ≈ the managed agent alone.
- **Session continuity.** Within an ADK session the proxy chains conversation
  (`previous_interaction_id`) and reuses the same sandbox (`environment.env_id`),
  so files/state persist across turns.
- **Graceful degradation.** If the managed agent isn't provisioned, or
  credentials/permissions fail, the tool returns a clear message and never crashes.

---

## Code breakdown

```
adk-agy-agent/
├── app/                          # ADK agent (the front door)
│   ├── agent.py                  # SkillProxyAgent: no-LLM proxy; streams the managed agent
│   ├── managed_agent.py          # stream_skill_task (SSE) + run_skill_task (one-shot);
│   │                             #   answer/trace extraction; graceful error handling
│   ├── platform_api.py           # REST URL helpers (global host: agents, interactions)
│   ├── config.py                 # env-driven config (project, agent id, timeouts, flags)
│   ├── fast_api_app.py           # A2A FastAPI server — Cloud Run entrypoint (scaffolded)
│   └── app_utils/                # telemetry + typing helpers (scaffolded)
│
├── Dockerfile                    # Cloud Run container image (scaffolded)
│
├── skills/                       # source of truth — one folder per skill
│   └── <id>/SKILL.md (+ scripts/, references/)   # registered into the Skill Registry
│
├── tools/
│   ├── register_skills.py          # zip + upsert each skills/<id>/ into the Skill Registry
│   └── bootstrap_managed_agent.py  # reconcile: mount each registered skill (SKILL_REGISTRY) on the agent
│
├── examples/
│   └── chat_with_agent.py        # standalone CLI: chat directly with the managed
│                                 #   agent via the Interactions API (uv inline-deps)
│
├── deployment/terraform/
│   ├── single-project/           # single-project infra (manual deploy)
│   │   ├── skills.tf             # ← register skills + reconcile agent (local-exec); no bucket
│   │   ├── service.tf            # Cloud Run service (app_sa, APP_URL); image updated by deploy
│   │   └── *.tf                  # scaffolded: APIs, telemetry, IAM, storage
│   └── shared/                   # BigQuery telemetry schema + completions SQL (used by telemetry.tf)
│
├── tests/
│   ├── unit/                     # test_managed_agent, test_bootstrap, test_register_skills (mocked)
│   ├── integration/              # scaffolded agent / runtime-app tests
│   └── eval/                     # agents-cli evalsets (basic.evalset.json)
│
├── agents-cli-manifest.yaml      # agents-cli project manifest
├── pyproject.toml                # uv project + dependencies
└── CLAUDE.md                     # AI-assisted development guide
```

### The request flow (`app/`)

1. `SkillProxyAgent` reads the user's message (no LLM).
2. `stream_skill_task` opens an SSE stream:
   `POST interactions` `{input, agent, background:true, store:true, stream:true}`
   (+ `previous_interaction_id` and `environment.env_id` for continuity).
3. It parses the `content.*` SSE events and **yields each chunk as an ADK event**,
   which the A2A executor streams to the caller — reasoning then answer, in order.
4. `managed_agent.py` also keeps `run_skill_task` (non-streaming: create → poll →
   answer + de-duplicated trace) for the local `agents-cli run`/playground path.

---

## Configuration

Set via environment (sensible defaults in `app/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | `rocketech-de-pgcp-sandbox` | GCP project |
| `MANAGED_AGENT_LOCATION` | `global` | Agents/Interactions API location (**must be `global`**) |
| `MANAGED_AGENT_ID` | `agy-skill-agent` | Fixed managed-agent ID |
| `SKILLS_LOCATION` | `us-central1` | Skill Registry location (register/bootstrap) |
| `INTERACT_TIMEOUT_S` | `300` | Max time for an interaction (stream + non-stream) |
| `INTERACT_POLL_INTERVAL_S` | `3` | Poll interval (non-streaming `run_skill_task` only) |
| `MANAGED_AGENT_SHOW_STEPS` | `1` | Include the step trace in non-streaming `run_skill_task` |
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
and its skills must be registered (see Deploy → bootstrap).

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

> Note: the deployed **ADK agent streams too** — `SkillProxyAgent` relays this same
> SSE stream through A2A (`app/managed_agent.py:stream_skill_task`). This script is
> just a minimal standalone version of the same thing (it uses the `google-genai`
> SDK directly instead of REST).

---

## Adding skills

Skills live in the repo `skills/` folder (one folder per skill — the source of
truth). A skill is a `SKILL.md` (YAML frontmatter + instructions) plus optional
helper files:

```
skills/<id>/SKILL.md
skills/<id>/scripts/...          # optional
skills/<id>/references/...       # optional
```

Add the folder, then register it and reconcile the agent:

```bash
GOOGLE_CLOUD_PROJECT=<id> uv run tools/register_skills.py        # upsert into the Skill Registry
GOOGLE_CLOUD_PROJECT=<id> uv run tools/bootstrap_managed_agent.py # mount it on the agent
```

(`terraform apply` runs both for you — see Deploy. The folder name becomes the
skill id: lowercase letters/numbers/hyphens, starts with a letter.) To remove a
skill, delete its folder and re-run both — and `DeleteSkill` it from the registry.

---

## How to deploy

```bash
gcloud config set project <your-project-id>
```

### 1. Provision infra + bootstrap the managed agent

```bash
cd deployment/terraform/single-project
terraform init
terraform apply
```

`skills.tf` runs `tools/register_skills.py` then `tools/bootstrap_managed_agent.py`
(via `local-exec`) — registering the repo's `skills/` into the Skill Registry and
creating/reconciling the managed agent to mount them. It re-runs whenever `skills/`
or the tool scripts change.

> Bootstrap manually instead (idempotent):
> ```bash
> GOOGLE_CLOUD_PROJECT=<id> uv run tools/register_skills.py
> GOOGLE_CLOUD_PROJECT=<id> uv run tools/bootstrap_managed_agent.py
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
  `base_environment: {type:"remote", sources:[{type:"SKILL_REGISTRY", source:
  "projects/<p>/locations/us-central1/skills/<id>", target:"/.agent/skills/<id>"}],
  network:{allowlist:[{domain:"*"}]}}`. One source per skill. The `network` block is
  required whenever any source is set, and **only `"*"` is accepted** (specific
  domains rejected — GCS and Skill Registry alike).
- **Skill Registry:** regional (`us-central1` | `europe-west4` | `us-east5`, not
  global). `CreateSkill`/`UpdateSkill`/`DeleteSkill` are LROs; skill body =
  `{displayName, description, zippedFilesystem}` (base64 of the zipped folder), with
  revisions. A global agent can reference a regional skill.
- **Patch:** one field per call — a combined update mask 400s, and `tools` is not
  patchable (set only at create).
- **Interactions:** `POST .../interactions` `{input, agent, background:true,
  store:true}` (**`background:true` required** for managed agents). Poll
  `GET .../interactions/{id}`; **status is lowercase**
  (`in_progress|completed|failed|...`).
- **Streaming:** add `stream:true` → `text/event-stream` (SSE). REST events are
  `content.start|delta|stop`, `interaction.start|complete`, `interaction.status_update`,
  terminated by `data: [DONE]`; text deltas are at `content.delta → delta.text`.
  (The `google-genai` SDK surfaces a different `step.*` schema for the same call.)
- **Continuity:** new interaction id per turn (chain via top-level
  `previous_interaction_id`); reuse the sandbox via `environment: {"env_id": ...}`.
- **Response:** answer is in `outputs[]` (a flat list; `text` items hold a
  plain-string `text`, interleaved with `function_call`/`function_result`). It
  contains streaming partials, so de-duplicate (drop a block contained in a later
  one). Tell the agent (system instruction) to state the actual result or it may
  reply with only a summary of steps.
```
