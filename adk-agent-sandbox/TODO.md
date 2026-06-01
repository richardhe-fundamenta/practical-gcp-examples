# TODO — unfinished work

The core agent loop is complete, evaluated (2/2 rubric cases at 1.0), and the harness
guarantees hold. Two pieces of production wiring remain. The Cloud Run service is
**currently deployed but non-functional** until these are done (the pinned sandbox and
its host Agent Engine were cleaned up — see item 1).

---

## 1. Sandbox lifecycle — per-session lazy get-or-create (BLOCKER for live deploy)

**Problem.** The sandbox is referenced by a single static `SANDBOX_RESOURCE_NAME` env
var, shared across all users/sessions. It has two failure modes:
- **Expiry / cleanup.** Agent Engine code-exec sandboxes have a TTL. The pinned sandbox
  *and its host reasoningEngine* were deleted, so `render_chart` now fails with
  `400 FAILED_PRECONDITION` (and the host engine returns `404 NOT_FOUND`).
- **No isolation.** A single shared, stateful sandbox can leak state across sessions/users.

**Decision (agreed):** per-session **lazy get-or-create**.
- On `render_chart`, look up a sandbox name stored in session state.
- If absent or stale (catch `404`/`FAILED_PRECONDITION`), create a fresh sandbox under a
  **persistent host Agent Engine**, store its name in session state, reuse within the session.
- This isolates users from each other and self-heals when a sandbox expires.

**Implementation sketch.**
- `app/sandbox/client.py`: add `get_or_create_sandbox(engine_name, tool_context)` that
  reads/writes a `sandbox_name` key in `tool_context.state`; wrap `execute_code` to retry
  once with a fresh sandbox on `404`/`FAILED_PRECONDITION`.
- `app/config.py`: replace `sandbox_resource_name` with `agent_engine_name` (the durable
  host engine), since sandboxes are now created on demand.
- `app/sandbox/render_tool.py`: pass `tool_context` through (already available).
- The host Agent Engine must be **persistent** — provision it in Terraform (item 2), not
  the throwaway minimal engine created earlier.
- Update `bootstrap/create_sandbox.py` / docs accordingly; update unit tests
  (`tests/unit/sandbox/test_client.py`) to cover the get-or-create + stale-retry paths.

---

## 2. Dedicated runtime service account + IAM in Terraform (agreed: option 2)

**Problem.** `agents-cli deploy` (no `infra single-project`) left the Cloud Run service
running as the **default compute SA** (`<num>-compute@developer.gserviceaccount.com`),
which has broad `roles/editor` + `roles/cloudbuild.builds.builder` — not least-privilege,
and not the intended identity.

**Decision (agreed):** use a dedicated **`app_sa`** (already defined in Terraform as
`${var.project_name}-app` → `analyst-harness-app`), grant it only the roles this agent
needs, and track everything in Terraform.

**Roles to ADD to `var.app_sa_roles`** in
`deployment/terraform/single-project/variables.tf` (current default already has
`roles/aiplatform.user`, `roles/logging.logWriter`, `roles/cloudtrace.agent`,
`roles/storage.admin`, `roles/serviceusage.serviceUsageConsumer`):

```hcl
# add to the app_sa_roles default list:
"roles/bigquery.jobUser",     # run validated queries (jobs)
"roles/bigquery.dataViewer",  # read allowlisted dataset(s)
# roles/aiplatform.user is ALREADY present — it covers the code-exec sandbox + model calls.
# The remote BigQuery MCP server uses the same google.auth ADC creds with the
# bigquery scope; bigquery.jobUser + dataViewer are sufficient. (No separate
# roles/mcp.toolUser binding was found in this project — verify if MCP later 403s.)
```

**Then:**
- Run `agents-cli infra single-project` to apply Terraform (creates `app_sa` + bindings,
  artifact/log bucket, telemetry). NOTE: this also sets `LOGS_BUCKET_NAME`, which makes
  `fast_api_app.py` use `GcsArtifactService` (persisted chart artifacts) instead of the
  in-memory fallback.
- Redeploy binding the SA explicitly:
  `agents-cli deploy --service-account analyst-harness-app@<project>.iam.gserviceaccount.com --update-env-vars "..."`
- Confirm `service.tf` wires the env vars (BQ_*, sandbox/engine) for the deployed revision;
  add them to the Terraform service config rather than passing `--update-env-vars` ad hoc.

---

## 3. Verify end-to-end on Cloud Run (after 1 + 2)

- `agents-cli run --url <service-url> --mode a2a "Chart monthly completed-order revenue by region from analyst_demo"`
- Assert trajectory reaches `run_validated_sql` → `render_chart` → PNG artifact, no errors
  in Cloud Logging. Then optionally register with Gemini Enterprise
  (`agents-cli publish gemini-enterprise`).

---

## Notes / smaller follow-ups

- **Gemini Enterprise inline image rendering** is a known rough edge
  ([adk-python#4273](https://github.com/google/adk-python/issues/4273)); the agent emits a
  correct `image/png` artifact, but GE may show it as an attachment rather than inline.
  Full inline rendering would mean adopting A2UI.
- The throwaway minimal Agent Engine + sandbox created during deployment debugging were
  cleaned up by GCP; don't rely on the old `SANDBOX_RESOURCE_NAME` in `.env`.
