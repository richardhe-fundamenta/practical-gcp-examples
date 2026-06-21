# a2a-with-gke-sandbox

An **A2A agent on Cloud Run** that runs **untrusted, LLM-generated Python in a GKE Agent
Sandbox** (Autopilot, gVisor), then renders the result — including charts — back inside
**Gemini Enterprise** via A2UI. The agent stays on Cloud Run (where your existing A2A
integration lives); GKE is used **only** as an isolated execution backend. Typical use: a user
uploads a CSV in Gemini Enterprise and asks for an analysis + chart.

## End-to-end journey (upload a CSV in GE → chart rendered in GE)

```
 Gemini Enterprise (chat)                         Cloud Run — ADK A2UI agent                       GKE Agent Sandbox            GCS
 ─────────────────────────                        ──────────────────────────                       ─────────────────            ───
 user uploads marketing.csv ──(1) message/send──▶ A2A request: file part + text
   + "chart spend by campaign"                          │
                                                   (2) load_skill("data-analysis")
                                                   (3) run_code(python) ── creates fresh ─────────▶ gVisor pod (no net/creds)
                                                          │                                          (4) write marketing.csv
                                                          │                                              + main.py to /app
                                                          │                                          (5) python3 main.py
                                                          │                                              pandas/matplotlib →
                                                          │                                              chart.png
                                                          │ ◀── (6) stdout + chart.png bytes ───────────┘
                                                   (7) upload chart.png ─────────────────────────────────────────────────────▶ a2ui-outputs/<uuid>/
                                                          │ ◀── (8) V4 signed URL (short TTL) ─────────────────────────────────┘
                                                   (9) hand model placeholder {{chart:chart.png}}
                                                  (10) model: send_a2ui_json_to_client(
                                                          title + "thinking" text + Image{{chart}})
                                                  (11) before_tool_callback swaps {{chart:..}}→signed URL
                                                  (12) emit A2UI as application/json+a2ui parts
                                                          in the COMPLETED task's artifacts
   chart card rendered  ◀──(13) tasks/get poll── task.artifacts (beginRendering + surfaceUpdate)
   (title / thinking / image)
```

1. **GE → A2A.** GE calls `message/send` (non-streaming; it polls `tasks/get`). The uploaded
   file rides as an A2A **file part**; the prompt as a text part.
2. **Skill (progressive disclosure).** The model calls `load_skill("data-analysis")` to fetch
   the contract for analyzing data + producing a chart.
3–6. **Sandbox execution.** `run_code` spins up a **fresh single-use gVisor pod**, writes the
   uploaded file + the model's `main.py` into `/app`, runs `python3 main.py` (pandas, numpy,
   matplotlib, … preinstalled), and reads back **stdout + any files the code wrote** (e.g.
   `chart.png`). No network, no credentials in the pod. On error the message is returned so the
   model can fix the code and retry (bounded).
7–9. **Host the image.** Image outputs are uploaded to a dedicated **GCS bucket** and a **V4
   signed URL** (short TTL, IAM `signBlob` — no key file) is minted. The model never sees the
   long URL: it gets a short **placeholder token** keyed by filename (`{{chart:chart.png}}`).
10–12. **A2UI render.** The model calls `send_a2ui_json_to_client` to build one A2UI v0.8
   surface — a **Column** of `title → thinking (its reasoning) → Image`. A `before_tool_callback`
   substitutes the placeholder for the real signed URL (so the model can't mangle it), and the
   executor emits the A2UI as `application/json+a2ui` parts in the **completed task's artifacts**.
13. **GE renders.** On its `tasks/get` poll, GE sees the completed task and renders
   `task.artifacts` inline in chat — the titled card with the reasoning and the chart image.

> Why artifacts + non-streaming: GE renders `task.artifacts` once a task is `completed` and
> ignores intermediate `working`/`history` events; under streaming it doesn't render the A2UI at
> all. So the agent advertises `streaming=false` and re-emits the result as a final artifact.
> (See `app/a2ui_support.py` and the in-repo notes for the full rationale.)

## Deployment topology

```
                 A2A request
                      │
                      ▼
        ┌──────────────────────────┐         control plane (create Sandbox CR)
        │  Cloud Run  (app plane)   │── IAM ─────────────────────────────────┐
        │  ADK agent + run_code     │                                        │
        │  k8s-agent-sandbox SDK    │── Direct VPC egress ──┐                ▼
        └──────────────────────────┘                       │   ┌──────────────────────────┐
                                                            │   │  GKE Autopilot cluster    │
                                                            ▼   │  (execution plane)        │
                                              ┌──────────────────────────┐  Agent Sandbox    │
                                              │ sandbox-router (int. LB)  │─▶ gVisor pod       │
                                              │ http://10.10.0.x:8080     │   (no creds,       │
                                              └──────────────────────────┘    no network)     │
                                                                  └──────────────────────────┘
```

- **App plane:** Cloud Run (ADK `adk_a2a`, ADK 2.x); the `run_code` tool ships model-written
  Python to the sandbox and returns stdout + generated files.
- **Execution plane:** GKE Agent Sandbox (managed GKE feature). Each run is a fresh,
  single-use gVisor pod with no credentials and default-deny networking.
- **Bridge:** Cloud Run reaches the cluster's **DNS-based control-plane endpoint** (IAM-gated)
  to create the sandbox, and the in-cluster **sandbox-router** (internal LB, via Direct VPC
  egress) to run code. The router is one-time setup, built from upstream `k8s-agent-sandbox`.

## Repository layout

```
app/                              # the agent (ADK, A2A, Cloud Run)
  agent.py                        # root agent, run_code tool, skill loader, file-upload + before_model hooks
  a2ui_support.py                 # A2UI rendering + legacy executor (emits result as a task artifact)
  sandbox/kube_auth.py            # Cloud Run → GKE control-plane auth (writes a kubeconfig)
  sandbox/client.py               # fresh-sandbox-per-request: write files + code, run, return outputs
skills/                           # SkillToolset skills (python-runner, data-analysis) — see skills/README.md
deployment/terraform/             # two stacks (platform + agent) + shared SQL — see its README
deployment/sandbox-runtime/       # the analytics image the sandbox runs code in — see its README
deployment/bootstrap/             # SandboxTemplate + router bootstrap (bootstrap.sh) — see its README
tools/session-viewer/             # local Streamlit GUI to browse runs from BigQuery on a timeline — see its README
tests/                            # unit/integration/eval — see tests/README.md
```

Terraform state is in GCS (one bucket, prefixes `gke-sandbox/` and `single-project/`). The
two stacks are split on purpose — the cluster is slow/rarely-changed, the Cloud Run agent
redeploys constantly. (Rationale for each non-obvious choice lives in the relevant source file.)

## Prerequisites

- **gcloud** + **`gke-gcloud-auth-plugin`** (`gcloud components install gke-gcloud-auth-plugin`)
- **terraform** ≥ 1.13, **kubectl**, **uv**
- A GCP project with billing; `gcloud auth login` and `gcloud auth application-default login`
- Roles to create GKE/Cloud Run/Artifact Registry/networking and run `gcloud builds` (Owner or equivalent)

```bash
export PROJECT=rocketech-de-pgcp-sandbox      # your project
export REGION=us-central1
gcloud config set project "$PROJECT"
```

## Setup (from nothing)

This is the happy-path sequence; for stack internals, vars, and design choices see
[`deployment/terraform/README.md`](deployment/terraform/README.md).

### 0. Terraform state bucket (one-time)

A backend can't bootstrap itself; create it out-of-band. Both stacks reference this bucket in
their `providers.tf` — update the name there if yours differs.

```bash
gcloud storage buckets create gs://${PROJECT}-tfstate \
  --project="$PROJECT" --location="$REGION" --uniform-bucket-level-access
gcloud storage buckets update gs://${PROJECT}-tfstate --versioning
```

### 1. Platform stack — VPC + private Autopilot cluster + Agent Sandbox (~10–15 min)

```bash
cd deployment/terraform/gke-sandbox      # set project_id/region in vars/env.tfvars
terraform init && terraform apply -var-file=vars/env.tfvars
gcloud container clusters get-credentials agent-sandbox --location "$REGION" --dns-endpoint
kubectl get crd | grep sandbox           # verify: sandboxtemplates.extensions.agents.x-k8s.io …
```

### 2. Bootstrap the SandboxTemplate + router

Builds + pushes the **analytics runtime** (`deployment/sandbox-runtime/`) and the router to
Artifact Registry, applies the `SandboxTemplate`, and deploys the router on an internal LB.
Prints `SANDBOX_API_URL`. (To change the packages available inside the sandbox, edit
[`deployment/sandbox-runtime/`](deployment/sandbox-runtime/README.md).) For the manifests, the
v1alpha1/internal-LB rationale, and per-step detail, see
[`deployment/bootstrap/README.md`](deployment/bootstrap/README.md).

```bash
cd ../../..
bash deployment/bootstrap/bootstrap.sh          # re-run with ROUTER_TAG=v2 to roll the router
kubectl get pods -l app=sandbox-router          # both 1/1 Running
```

### 3. Agent stack — Cloud Run (feed in the router URL from step 2)

```bash
cd deployment/terraform/single-project
terraform init && terraform apply -var-file=vars/env.tfvars \
  -var sandbox_api_url=http://10.10.0.3:8080
```

Creates the Cloud Run service (placeholder image, `ignore_changes` on the image + gcloud's
`client`/`client_version` metadata), the app SA (`roles/container.developer`), Direct VPC egress,
and all the service env vars — `SANDBOX_*`, `GKE_ENDPOINT`, and the bucket vars
(`LOGS_BUCKET_NAME`, `CHART_BUCKET`, `UPLOADS_BUCKET`, `SIGNING_SERVICE_ACCOUNT`). Terraform owns
the service config; `deploy-image.sh` only swaps the image.

### 4. Build + deploy the agent image

```bash
cd ../../..
bash deployment/deploy-image.sh        # build + push (tagged by git SHA), then swap the image only
```

`deploy-image.sh` builds the Dockerfile, pushes to Artifact Registry tagged with the git short
SHA, and runs `gcloud run services update --image` — it changes **only the image**, leaving
Terraform the single owner of the service config (SA, VPC egress, env, scaling), so nothing
drifts. Cloud Run still creates a revision per deploy; roll back with
`gcloud run services update-traffic --to-revisions=<rev>=100`.

> Don't use `agents-cli deploy` here — it also sets its own scaling/env/SA, which fights the
> Terraform-managed config on the next `apply`. The Dockerfile must include `skills/` (it does).

### 5. Test end-to-end

The service is private and the A2A endpoint is `/a2a/app`. Use a task that *requires*
execution (a hash) so the model can't fake it; check the `run_code` result in the response
`history`, not just the final text.

```bash
SERVICE_URL=$(gcloud run services describe a2a-with-gke-sandbox --region "$REGION" --format='value(status.url)')
curl -s -X POST "$SERVICE_URL/a2a/app" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send","params":{"message":{"role":"user","parts":[{"kind":"text","text":"Using Python, print the sha256 hex digest of the string gke-sandbox-2026 and nothing else."}],"messageId":"h1","kind":"message"}}}'

python3 -c "import hashlib; print(hashlib.sha256(b'gke-sandbox-2026').hexdigest())"
# expect the run_code result to equal: 57b569f2364fa9aea392766cef6929025a9d133cd1ce5d43d4ad2214aea2bf9e
```

## Local development

The **sandbox path can't run from your laptop**: `run_code` reaches the in-cluster router over an
**internal load balancer** (`10.10.0.x`, via the Cloud Run service's Direct VPC egress), and there's
no route to it from outside the VPC. So `agents-cli playground` will start the agent locally but any
`run_code` call fails — **end-to-end testing happens against the deployed Cloud Run service** (the
auth'd `POST /a2a/app` in [§5](#5-test-end-to-end), or via Gemini Enterprise).

What you *can* do locally:

```bash
uv run pytest tests/sandbox      # unit tests (sandbox SDK / auth / A2UI are mocked)
agents-cli lint                  # code quality

# Inspect real runs on a timeline (reads BigQuery; needs ADC + BigQuery read access):
gcloud auth application-default login
cd tools/session-viewer && uv run streamlit run app.py      # http://localhost:8501
```

See [`tools/session-viewer/`](tools/session-viewer/) — a Streamlit GUI to pick a historical session
and see the whole run (user message, model thinking, every tool call + response, errors) on a
timeline. It's the main way to debug behaviour, since you can't reproduce the sandbox path locally.

## Capabilities & behavior

- **Skills:** loaded via ADK `SkillToolset` — only name+description upfront; full `SKILL.md`
  fetched at runtime via `load_skill` (progressive disclosure). Ships `python-runner`
  (generic) and `data-analysis` (charts/reports from data). Authoring: [`skills/README.md`](skills/README.md).
- **File uploads:** files attached to a turn are written into the sandbox working dir (≤5 MB
  each); the model opens them by name (`open("data.csv")`), no inlining. They also **persist
  across turns** of the conversation — stashed in GCS (`session-uploads/<conversation_id>/`,
  7-day lifecycle) and re-hydrated into each fresh sandbox — so a follow-up like "now make it a
  pie chart" still has the file even though Gemini Enterprise only attaches it on the upload turn.
  The model is told to ask for a re-attach rather than reconstruct data if a file is missing.
- **File outputs:** files the code writes are read back (≤5 MB each, runtime-image files
  excluded). **Images** (e.g. `chart.png`) are hosted in GCS and rendered inline via A2UI (see
  below); other files (`report.xlsx`/`.csv`) come back as A2A attachments. Write a file, don't
  print bytes.
- **A2UI chart rendering (Gemini Enterprise):** charts display inline in GE as an A2UI v0.8
  surface (`title → thinking → Image`). The image `url` is a short-TTL **V4 signed URL**; the
  model only ever copies a filename placeholder (`{{chart:chart.png}}`) that a
  `before_tool_callback` swaps for the real URL. The result is emitted in the **completed task's
  artifacts** (what GE renders on its poll); `streaming=false`. A bounded retry
  (`A2UI_RENDER_MAX_ATTEMPTS`, default 2) re-runs on a fresh session if Gemini returns a
  `MALFORMED_FUNCTION_CALL` on the final render. See `app/a2ui_support.py`.
- **Auto-fix retries:** on a sandbox error the model receives the error and retries (rewrites
  the code), bounded to 3 attempts per turn (`RUN_CODE_MAX_ATTEMPTS`).
- **Analytics runtime:** the sandbox image ships pandas, numpy, polars, pyarrow, duckdb,
  scipy, scikit-learn, statsmodels, matplotlib, seaborn, altair, plotly, openpyxl (see
  `deployment/sandbox-runtime/pyproject.toml`).
- **Reasoning:** the model's reasoning is surfaced as a **"thinking" text section inside the
  A2UI card** (GE doesn't show the thinking tab on the non-streaming poll path). Thought
  summaries are also emitted (`include_thoughts`).
- **Sandbox lifecycle:** fresh sandbox per request (no session reuse).

## Observability

Traces export to **Cloud Trace** under service `a2a-with-gke-sandbox` — the full tree per
request (model turns, `load_skill`, `run_code`, sandbox call, tokens):
`https://console.cloud.google.com/traces/list?project=$PROJECT`.

GenAI logs also land in **BigQuery** (`<project>.a2a_with_gke_sandbox_telemetry.completions_view`).
Reading that with SQL is tedious, so use the local **`tools/session-viewer/`** Streamlit GUI to see
any run on a timeline — see [Local development](#local-development) for how to run it.

## Gotchas & lessons learned

These are the non-obvious things that cost time while building this. They're written down so
they don't cost you any. Everything here is about young, fast-moving features fitting together —
none of it is a knock on any product; it's just where the edges are today (mid-2026).

**Gemini Enterprise + A2UI rendering**

- **Put the result in the *completed task's* artifacts.** When GE drives the agent it polls
  `tasks/get` and renders `task.artifacts` once the task is `completed`; it doesn't replay the
  `working` status messages or `history`. If your A2UI only ever lands in an intermediate
  `working` event (the default flow), GE shows the thinking trace and then nothing. The fix is
  to aggregate the run and re-emit the result as a final `TaskArtifactUpdateEvent(last_chunk=True)`
  before `completed` (see `app/a2ui_support.py:_handle_request`).
- **Force the legacy executor path.** GE activates the "new ADK integration" A2A extension,
  which routes `A2aAgentExecutor` to an internal implementation and bypasses your subclass
  overrides — so a custom `_handle_request`/`_prepare_session` silently never runs. Pass
  `use_legacy=True` to keep your code in the loop.
- **Streaming + A2UI doesn't render in GE yet.** With `streaming=true` the A2UI surface doesn't
  display, so the card advertises `streaming=false` and GE uses the polling path. A side effect
  is that GE's "thinking" tab collapses (the agent finishes within a poll), so we surface the
  model's reasoning as a **`thinking` text section inside the A2UI card**, just above the chart.
- **GE renders A2UI v0.8.** Build the surface against the v0.8 standard catalog and advertise
  the `…/a2a-extension/a2ui/v0.8` extension on the card.
- **The agent card is read at registration time.** If you change a card capability (e.g.
  `streaming`, or add the A2UI extension), GE keeps using the cached card until you
  **re-register**. A confusing symptom is the streaming endpoint erroring after you set
  `streaming=false`, because GE still thinks it's `true`.
- **Image components rendering from external URLs can be finicky** — other components (Text,
  Card) are reliable. If a chart image won't show while text does, that's the place to look
  (a native chart component or inline data is the fallback).

**ADK ⇄ A2A session state**

- **`session.state` isn't reliably live when the A2A event converter runs.** A value a tool
  wrote (`tool_context.state[...]`) may be missing from the snapshot the converter reads, and a
  non-JSON-serializable object (like the A2UI catalog) can drop out entirely even though the
  in-process toolset saw it fine. So: pin fixed objects directly (we pass
  `A2uiPartConverter(_DEFAULT_CATALOG)` instead of reading the catalog from state), and do
  value substitution in a `before_tool_callback` (where tool-execution state *is* live) rather
  than in the converter.

**Working with the model**

- **Don't hand the model an opaque token to copy verbatim.** Given a random
  `{{chart:ab12}}` placeholder, the model "helpfully" rewrites it from the filename
  (`{{chart:chart.png}}`), so the lookup misses. Key the placeholder by filename and it matches
  what the model naturally produces.
- **Large structured tool calls occasionally come back malformed.** Gemini intermittently
  returns `MALFORMED_FUNCTION_CALL` on the big final `send_a2ui` call. A bounded retry on a
  fresh session (`A2UI_RENDER_MAX_ATTEMPTS`) makes it reliable; keep the payload (e.g. the
  thinking text) reasonably short to reduce the odds.
- **A missing file becomes a silent fabrication if you let it.** On a follow-up turn the user
  doesn't re-attach the file, so a naive `run_code` hits `FileNotFoundError` — and the model will
  "fix" it by **hardcoding the data from memory** and charting that (looks real, silently wrong).
  We close this by persisting uploads (below) *and* returning "ask the user to re-attach" instead
  of "fix the code" when no file is available, plus a skill rule against reconstructing data.

**Uploads across turns**

- **A2A/Gemini Enterprise attaches a file only on the upload turn**, and the sandbox is fresh per
  request — so follow-ups ("now make it a pie chart") arrive with no file. Persist uploads
  yourself: we stash them in GCS keyed by conversation and re-hydrate every turn (`session_files.py`).
- **`conversation_id` == A2A `contextId` == ADK `session_id`** — all the same string (ADK sets
  `session_id = request.context_id`), and GE keeps one across a conversation's turns. So it's the
  natural, stable key for per-conversation storage (and the grouping key in the BigQuery view).

**Registering with Gemini Enterprise**

- **Agent creation is rate-quota'd.** Repeated `agents-cli publish` runs can hit
  `429 RESOURCE_EXHAUSTED "Agent creation quota exceeded"` — and because the idempotent match
  often misses, each run *creates a new* agent rather than updating, burning more quota. Deleting
  existing agents doesn't restore it (it's a creation-*rate* limit, not a count cap). Register
  once; if you must iterate, update the existing registration in the console.

**GKE Agent Sandbox / runtime**

- **Private nodes can't pull from `registry.k8s.io`.** The stock sandbox runtime image times out
  on a private cluster, so we **build our own analytics runtime** (uv + pandas/numpy/matplotlib/…)
  into Artifact Registry and point the `SandboxTemplate` at it.
- **The runtime is shell-less; commands run argv-style.** Pipe tricks and `&&` don't work — write
  `main.py` into the pod and run `python3 main.py`, and surface `stderr`/`exit_code` yourself.
- **Diff the working dir against a baseline.** Reading "files the code wrote" naively also picks
  up the runtime image's own files (e.g. `pyproject.toml`). Snapshot the dir *before* the run and
  exclude that baseline.
- **`KUBECONFIG` must be set before importing the sandbox SDK.** The Kubernetes client freezes
  its config path at import, so write the kubeconfig and set the env var first
  (`app/sandbox/kube_auth.py`), or you get `Invalid kube-config file`.

**Terraform / infra**

- **Pin `google`/`google-beta` to `>= 7.37`** — earlier providers don't expose
  `addons_config.agent_sandbox_config`.
- **The DNS-based control-plane endpoint** lets Cloud Run create sandboxes over an IAM-gated,
  public-trust-TLS endpoint without a bastion or VPC peering — nodes stay private. It's the piece
  that keeps the "app on Cloud Run, isolation on GKE" split simple.
- **Let Cloud Logging own the sink's BigQuery schema.** It auto-evolves the table, so put
  `lifecycle { ignore_changes = [schema] }` on the table or Terraform will plan destructive
  replacements.
- **Don't let Terraform and `agents-cli deploy` both manage the Cloud Run service.** They fight
  over scaling/env/SA. Here Terraform owns the config and `deployment/deploy-image.sh` only swaps
  the image.

## Production hardening (shortcuts taken here)

### Router runs unauthenticated on an internal LB

The sandbox router is published on a GKE **internal** LoadBalancer (`10.10.0.x`) and runs with
`ALLOW_UNAUTHENTICATED_ROUTER=true` — it does **no auth check of its own**. The only thing
protecting it is network reachability.

**What that means:** the router is *not* on the public internet (the LB is internal and the nodes
are private), but **anything that can reach that private IP inside the VPC can call it with no
credential** — other workloads in the VPC, anything with Direct VPC egress into that network, or an
attacker who gains a foothold on a VM/pod. The router is the data-plane proxy to sandbox pods, so a
caller can **run code in and read/write files of sandbox pods** without authenticating.

**How bad is it?** Bounded, but real. Blast radius is limited by design — sandbox pods have **no
network and no mounted credentials**, so this is mostly *arbitrary compute abuse* and a foothold,
not direct data exfiltration. And **creating** a sandbox still goes through the IAM-gated GKE
control-plane (the app SA needs `roles/container.developer`); only the *run-code* path through the
router is open. Net: low risk if your VPC is trusted and tightly scoped; not something to rely on
network isolation alone for in a shared or sensitive network.

**Fix:** set `ROUTER_AUTH_TOKEN` from a Kubernetes Secret (remove `ALLOW_UNAUTHENTICATED_ROUTER`),
have the Cloud Run agent send it on every request, and add a `NetworkPolicy`/firewall that only
admits the Cloud Run egress range to the router — defense in depth: restrict *who can connect*
**and** require a credential. See `deployment/bootstrap/README.md` for the router config.

### App SA has broad permissions

The app service account holds `roles/container.developer` (broad cluster access) → tighten to a
custom RBAC role scoped to just the Sandbox resources it needs to create/use.

## Teardown

```bash
cd deployment/terraform/single-project && terraform destroy -var-file=vars/env.tfvars -var sandbox_api_url=unused
kubectl delete -f deployment/bootstrap/router.yaml -f deployment/bootstrap/sandbox-template.yaml
cd ../gke-sandbox && terraform destroy -var-file=vars/env.tfvars
gcloud storage rm -r gs://${PROJECT}-tfstate        # optional
```

## Credits

The A2UI integration with Gemini Enterprise here is based on
[**A guide to Gemini Enterprise and A2UI integration**](https://cloud.google.com/blog/topics/developers-practitioners/guide-to-gemini-enterprise-and-a2ui-integration)
by **Dave Wang** and **Yuan Tian** — that's where the A2UI-for-Gemini-Enterprise approach was
learned. Credit to them.
