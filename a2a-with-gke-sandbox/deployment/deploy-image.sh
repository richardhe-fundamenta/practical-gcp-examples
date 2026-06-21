#!/usr/bin/env bash
# Build the agent image and update ONLY the Cloud Run image.
#
# Use this instead of `agents-cli deploy` so Terraform stays the single owner of the service
# config (service account, VPC egress, env vars, scaling) and nothing drifts. The image is
# tagged with the git short SHA for a clean, reproducible history + easy rollback.
set -euo pipefail

PROJECT="${PROJECT:-rocketech-de-pgcp-sandbox}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-a2a-with-gke-sandbox}"
AR_REPO="${AR_REPO:-cloud-run-source-deploy}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # the agent project root (has Dockerfile)

TAG="$(git -C "${REPO_ROOT}" rev-parse --short HEAD)"
git -C "${REPO_ROOT}" diff --quiet || TAG="${TAG}-dirty"  # flag uncommitted builds
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/${SERVICE}:${TAG}"

echo "==> Ensuring Artifact Registry repo '${AR_REPO}'..."
gcloud artifacts repositories create "${AR_REPO}" --repository-format=docker \
  --location="${REGION}" --project="${PROJECT}" 2>/dev/null || true

echo "==> Building + pushing ${IMAGE} (Cloud Build, uses the Dockerfile)..."
gcloud builds submit "${REPO_ROOT}" --tag "${IMAGE}" --project "${PROJECT}"

echo "==> Updating Cloud Run service image only (config stays Terraform-managed)..."
gcloud run services update "${SERVICE}" \
  --image "${IMAGE}" --region "${REGION}" --project "${PROJECT}"

echo ""
echo "Deployed ${SERVICE} -> ${IMAGE}"
echo "Rollback: gcloud run services update ${SERVICE} --image <...>:<old-sha> --region ${REGION}"
echo "      or: gcloud run services update-traffic ${SERVICE} --to-revisions <REVISION>=100 --region ${REGION}"
