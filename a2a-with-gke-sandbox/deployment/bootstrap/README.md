# GKE Bootstrap: SandboxTemplate + Router

This directory contains the manifests and script needed to bootstrap the
`agent-sandbox` GKE cluster after the gke-sandbox Terraform stack has been applied.

## What it does

1. Fetches GKE credentials via the DNS-based control-plane endpoint.
2. Ensures the Artifact Registry repository exists.
3. Builds and pushes the sandbox-router Docker image using Cloud Build.
4. Builds and pushes the **analytics sandbox runtime** image (`deployment/sandbox-runtime/` — the
   FastAPI server + the data stack the sandbox runs on). Edit that folder's `pyproject.toml` to
   change the packages available inside the sandbox.
5. Applies the `SandboxTemplate` CRD manifest (`sandbox-template.yaml`), pointing at that runtime image.
6. Deploys the sandbox-router as an internal LoadBalancer Service + Deployment (`router.yaml`).
7. Waits for the internal LB IP and prints `SANDBOX_API_URL` for use in the agent stack.

## Prerequisites

- `gcloud` CLI authenticated with access to project `rocketech-de-pgcp-sandbox`.
- `gke-gcloud-auth-plugin` installed (required for the DNS-endpoint credential fetch).
- `kubectl` in PATH.
- `envsubst` in PATH (part of `gettext`; available via `brew install gettext` on macOS).
- The gke-sandbox Terraform stack must have been applied first (cluster must be running).

## Run

From the repo root:

```bash
bash deployment/bootstrap/bootstrap.sh
```

You can override defaults with env vars:

```bash
PROJECT=rocketech-de-pgcp-sandbox \
REGION=us-central1 \
CLUSTER=agent-sandbox \
AR_REPO=agent-sandbox \
ROUTER_TAG=v1 \
bash deployment/bootstrap/bootstrap.sh
```

## Files

| File | Description |
|---|---|
| `bootstrap.sh` | Main runnable script — runs all steps in order |
| `sandbox-template.yaml` | `SandboxTemplate` manifest (v1alpha1) |
| `router.yaml` | `ServiceAccount` + internal LB `Service` + `Deployment` for the sandbox router |
| `router/Dockerfile` | Dockerfile for the sandbox router (copied verbatim from upstream) |
| `router/sandbox_router.py` | FastAPI reverse-proxy application (copied verbatim from upstream) |
| `router/requirements.txt` | Pinned + hashed Python dependencies (copied verbatim from upstream) |

## Output

The script prints:

```
SANDBOX_API_URL=http://<INTERNAL_LB_IP>:8080
```

Feed this to the agent (single-project) Terraform stack:

```bash
# Option A: var flag
terraform apply \
  -var sandbox_api_url=http://<IP>:8080 \
  -var-file=vars/env.tfvars

# Option B: add to vars/env.tfvars
sandbox_api_url = "http://<IP>:8080"
```

## Known shortcuts and caveats

### v1alpha1 vs upstream v1beta1

The upstream `kubernetes-sigs/agent-sandbox` example uses
`apiVersion: extensions.agents.x-k8s.io/v1beta1` for `SandboxTemplate`.
This cluster's installed controller expects **v1alpha1**. The manifests here
use `v1alpha1` exclusively. If/when the controller is upgraded to v1beta1,
update the `apiVersion` in `sandbox-template.yaml`.

### Internal LoadBalancer (not ClusterIP)

The upstream `sandbox_router.yaml` uses `type: ClusterIP`. This bootstrap
changes the Service to `type: LoadBalancer` with annotation
`networking.gke.io/load-balancer-type: "Internal"`. This is necessary because
the Cloud Run–based agent connects to the router over Direct VPC egress, which
requires a stable RFC-1918 IP on the VPC — a ClusterIP is not reachable from
outside the cluster.

### Unauthenticated router (cut-B shortcut)

`ALLOW_UNAUTHENTICATED_ROUTER: "true"` is set in the router Deployment.
This is safe because the internal LB is not reachable from the public internet
(only from the VPC). For production hardening: remove that env var and instead
set `ROUTER_AUTH_TOKEN` from a Kubernetes Secret, and pass the token from the
Cloud Run agent.

### Router RBAC

The router resolves sandbox endpoints by constructing the in-cluster DNS name
(`<sandbox-id>.<namespace>.svc.cluster.local`) — it does not call the K8s API
to list or get Sandbox/Pod resources. Therefore no `Role`/`RoleBinding` is
strictly required. A `ServiceAccount` is created as a named identity (good
practice; required if RBAC is extended later).
