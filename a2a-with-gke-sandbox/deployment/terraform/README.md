# Terraform

Two stacks, split on purpose — the cluster is slow and rarely changes, the Cloud Run agent
redeploys constantly — plus a small `shared/` of SQL/schema used by the telemetry resources.

```
gke-sandbox/      PLATFORM stack: VPC + private Autopilot cluster + Agent Sandbox add-on
single-project/   AGENT stack:    Cloud Run + app SA/IAM + telemetry (reads platform outputs)
shared/           completions.sql (the BigQuery view) + genai_logs_schema.json
```

State lives in **GCS** (one bucket, prefixes `gke-sandbox/` and `single-project/`). Both stacks
reference the bucket in their `providers.tf` — update the name there if yours differs.

## Apply order

The happy path (with exact commands) is in the repo-root [`README.md`](../../README.md) **Setup**
section. In short:

1. Create the state bucket (out-of-band — a backend can't bootstrap itself).
2. `gke-sandbox/` → `terraform apply -var-file=vars/env.tfvars` (~10–15 min).
3. Bootstrap the SandboxTemplate + router (see [`../bootstrap/`](../bootstrap/)) → get `SANDBOX_API_URL`.
4. `single-project/` → `terraform apply -var-file=vars/env.tfvars -var sandbox_api_url=http://<IP>:8080`.

`single-project` reads platform outputs via `remote_state.tf`, so the platform stack must exist first.

## What each stack creates

- **`gke-sandbox/`** — `network.tf` (VPC, private nodes), `gke_sandbox.tf` (Autopilot cluster with
  `addons_config.agent_sandbox_config` + the DNS-based control-plane endpoint), `apis.tf`, outputs.
- **`single-project/`** — `service.tf` (Cloud Run + Direct VPC egress + `SANDBOX_*`/`GKE_ENDPOINT`/
  signing env), `iam.tf` (app SA: `roles/container.developer` + `serviceAccountTokenCreator` on
  itself for signed URLs), `storage.tf` (logs + chart-output + user-uploads buckets), `telemetry.tf` (genai log
  sink → BigQuery, using `shared/`).

## Design choices worth knowing

- **Provider pin `>= 7.37`** for `google`/`google-beta` — earlier versions don't expose
  `addons_config.agent_sandbox_config`.
- **DNS-based control-plane endpoint** (not IP/bastion) — IAM-gated, public-trust TLS; lets Cloud
  Run create sandboxes without VPC peering while nodes stay private.
- **`ignore_changes`** on the Cloud Run image (the image is shipped by `deployment/deploy-image.sh`,
  not Terraform) and on the genai BigQuery table `schema` (Cloud Logging auto-evolves it).

See the repo-root README **Gotchas** for the reasoning behind these.
