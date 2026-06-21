#!/usr/bin/env bash
# bootstrap.sh — Apply SandboxTemplate + deploy sandbox-router to the GKE cluster.
# Run AFTER the gke-sandbox Terraform stack has been applied.
# Usage: bash deployment/bootstrap/bootstrap.sh
# The script prints SANDBOX_API_URL at the end; pass it to the agent stack apply.
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — override via env vars if needed
# ---------------------------------------------------------------------------
PROJECT="${PROJECT:-rocketech-de-pgcp-sandbox}"
REGION="${REGION:-us-central1}"
CLUSTER="${CLUSTER:-agent-sandbox}"
AR_REPO="${AR_REPO:-agent-sandbox}"
ROUTER_TAG="${ROUTER_TAG:-v1}"
SANDBOX_RUNTIME_TAG="${SANDBOX_RUNTIME_TAG:-v1}"

ROUTER_IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/sandbox-router:${ROUTER_TAG}"
# Our analytics runtime image (built from deployment/sandbox-runtime/). Lives in AR, which
# the private nodes can pull via Private Google Access (registry.k8s.io is not reachable).
export SANDBOX_IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/sandbox-runtime:${SANDBOX_RUNTIME_TAG}"

# ---------------------------------------------------------------------------
# Step 1: Authenticate kubectl against the GKE cluster
# ---------------------------------------------------------------------------
echo "==> [1/6] Fetching GKE credentials for cluster '${CLUSTER}' in '${REGION}'..."
gcloud container clusters get-credentials "${CLUSTER}" \
  --location "${REGION}" \
  --project "${PROJECT}" \
  --dns-endpoint

# ---------------------------------------------------------------------------
# Step 2: Ensure Artifact Registry repo exists
# ---------------------------------------------------------------------------
echo "==> [2/6] Ensuring Artifact Registry repo '${AR_REPO}' exists in '${REGION}'..."
gcloud artifacts repositories create "${AR_REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --project="${PROJECT}" \
  --description="Agent sandbox router images" 2>&1 \
  | grep -v "ALREADY_EXISTS" || true
echo "    AR repo ready: ${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}"

# ---------------------------------------------------------------------------
# Step 3: Build + push the router image via Cloud Build
# ---------------------------------------------------------------------------
echo "==> [3/6] Building + pushing router image: ${ROUTER_IMAGE}"
echo "    (uses Cloud Build — submits deployment/bootstrap/router/ as build context)"
# Run from repo root so the path is stable regardless of cwd
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
gcloud builds submit "${REPO_ROOT}/deployment/bootstrap/router" \
  --tag "${ROUTER_IMAGE}" \
  --project "${PROJECT}"

# ---------------------------------------------------------------------------
# Step 4: Build + push the analytics sandbox runtime image (FastAPI server + data stack)
# ---------------------------------------------------------------------------
echo "==> [4/7] Building analytics sandbox runtime: ${SANDBOX_IMAGE} (via Cloud Build)..."
gcloud builds submit "${REPO_ROOT}/deployment/sandbox-runtime" \
  --tag "${SANDBOX_IMAGE}" \
  --project "${PROJECT}"

# ---------------------------------------------------------------------------
# Step 5: Apply the SandboxTemplate (v1alpha1), pointing at the mirrored image
# ---------------------------------------------------------------------------
echo "==> [5/7] Applying SandboxTemplate (apiVersion: extensions.agents.x-k8s.io/v1alpha1)..."
SANDBOX_IMAGE="${SANDBOX_IMAGE}" envsubst '${SANDBOX_IMAGE}' \
  < "${SCRIPT_DIR}/sandbox-template.yaml" \
  | kubectl apply -f -

# ---------------------------------------------------------------------------
# Step 5: Apply the router Service + Deployment (internal LB)
# ---------------------------------------------------------------------------
echo "==> [6/7] Applying sandbox-router (internal LoadBalancer Service + Deployment)..."
# Only ROUTER_IMAGE is substituted; other dollar-signs in the file are escaped.
ROUTER_IMAGE="${ROUTER_IMAGE}" envsubst '${ROUTER_IMAGE}' \
  < "${SCRIPT_DIR}/router.yaml" \
  | kubectl apply -f -

# ---------------------------------------------------------------------------
# Step 6: Wait for internal LB IP
# ---------------------------------------------------------------------------
echo "==> [7/7] Waiting for internal LoadBalancer IP on service 'sandbox-router-svc'..."
echo "    (This may take 1-2 minutes while GCP provisions the internal LB)"
LB_IP=""
for i in $(seq 1 60); do
  LB_IP=$(kubectl get svc sandbox-router-svc \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  if [[ -n "${LB_IP}" ]]; then
    break
  fi
  echo "    ... attempt ${i}/60 — waiting 5s"
  sleep 5
done

if [[ -z "${LB_IP}" ]]; then
  echo ""
  echo "ERROR: Timed out waiting for internal LB IP after 5 minutes."
  echo "  Check: kubectl get svc sandbox-router-svc"
  echo "  Check: kubectl describe svc sandbox-router-svc"
  exit 1
fi

SANDBOX_API_URL="http://${LB_IP}:8080"

echo ""
echo "============================================================"
echo "Bootstrap complete!"
echo ""
echo "  SANDBOX_API_URL=${SANDBOX_API_URL}"
echo ""
echo "Use this URL when applying the agent (single-project) stack:"
echo ""
echo "  Option A — Terraform var flag:"
echo "    terraform apply \\"
echo "      -var sandbox_api_url=${SANDBOX_API_URL} \\"
echo "      -var-file=vars/env.tfvars"
echo ""
echo "  Option B — add to vars/env.tfvars:"
echo "    sandbox_api_url = \"${SANDBOX_API_URL}\""
echo "    then: terraform apply -var-file=vars/env.tfvars"
echo "============================================================"
