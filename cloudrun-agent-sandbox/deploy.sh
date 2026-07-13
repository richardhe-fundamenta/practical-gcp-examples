#!/bin/bash
set -e

PROJECT_ID="rocketech-de-pgcp-sandbox"
REGION="us-east1"
SERVICE_NAME="cloudrun-agent-sandbox"

echo "Deploying ${SERVICE_NAME} to project ${PROJECT_ID} in region ${REGION} with Cloud Run Sandbox enabled..."

gcloud beta run deploy ${SERVICE_NAME} \
  --project ${PROJECT_ID} \
  --region ${REGION} \
  --source . \
  --memory 4Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --concurrency 8 \
  --no-allow-unauthenticated \
  --no-cpu-throttling \
  --update-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=global,AGENT_VERSION=0.1.0" \
  --add-volume=name=session-bucket,type=cloud-storage,bucket=${PROJECT_ID}-${SERVICE_NAME}-sessions \
  --add-volume-mount=volume=session-bucket,mount-path=/sessions \
  --sandbox-launcher \
  --quiet
