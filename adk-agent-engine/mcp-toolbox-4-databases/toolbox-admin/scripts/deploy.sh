#!/bin/bash
# Deployment script for MCP Toolbox to Cloud Run

set -e

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Validate required environment variables
if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: PROJECT_ID is required. Set it in .env or export it."
    exit 1
fi

# Set defaults
REGION=${REGION:-us-central1}
SERVICE_NAME=${CLOUD_RUN_SERVICE_NAME:-toolbox}
IMAGE_NAME=${IMAGE_NAME:-toolbox-admin}
IMAGE_TAG=${IMAGE_TAG:-latest}
REGISTRY=${CONTAINER_REGISTRY:-gcr.io}
MEMORY=${CLOUD_RUN_MEMORY:-512Mi}
CPU=${CLOUD_RUN_CPU:-1}
MAX_INSTANCES=${CLOUD_RUN_MAX_INSTANCES:-10}
MIN_INSTANCES=${CLOUD_RUN_MIN_INSTANCES:-0}
TIMEOUT=${CLOUD_RUN_TIMEOUT:-300s}
CONCURRENCY=${CLOUD_RUN_CONCURRENCY:-80}

# Construct full image path
FULL_IMAGE_PATH="$REGISTRY/$PROJECT_ID/$IMAGE_NAME:$IMAGE_TAG"

echo "========================================"
echo "MCP Toolbox - Cloud Run Deployment"
echo "========================================"
echo "Project ID:    $PROJECT_ID"
echo "Region:        $REGION"
echo "Service Name:  $SERVICE_NAME"
echo "Image:         $FULL_IMAGE_PATH"
echo "Memory:        $MEMORY"
echo "CPU:           $CPU"
echo "Concurrency:   $CONCURRENCY"
echo "Min Instances: $MIN_INSTANCES"
echo "Max Instances: $MAX_INSTANCES"
echo "Timeout:       $TIMEOUT"
echo "========================================"

# Confirm deployment
read -p "Deploy to Cloud Run? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# Set the active project
echo "Setting GCP project to $PROJECT_ID..."
gcloud config set project "$PROJECT_ID"

# Build and push the container image
echo "========================================"
echo "Building container image..."
echo "========================================"

gcloud builds submit \
    --tag "$FULL_IMAGE_PATH" \
    --timeout=20m \
    .

if [ $? -ne 0 ]; then
    echo "ERROR: Container build failed"
    exit 1
fi

echo "========================================"
echo "Deploying to Cloud Run..."
echo "========================================"

# Deploy to Cloud Run
gcloud run deploy "$SERVICE_NAME" \
    --image "$FULL_IMAGE_PATH" \
    --region "$REGION" \
    --platform managed \
    --memory "$MEMORY" \
    --cpu "$CPU" \
    --min-instances "$MIN_INSTANCES" \
    --max-instances "$MAX_INSTANCES" \
    --timeout "$TIMEOUT" \
    --concurrency "$CONCURRENCY" \
    --set-env-vars "PROJECT_ID=$PROJECT_ID" \
    --set-env-vars "REGISTRY_DATASET=${REGISTRY_DATASET:-config}" \
    --set-env-vars "REGISTRY_TABLE=${REGISTRY_TABLE:-query_registry}" \
    --set-env-vars "TOOLBOX_PORT=8080" \
    --set-env-vars "TOOLBOX_ADDRESS=0.0.0.0" \
    --set-env-vars "BIGQUERY_SOURCE_NAME=${BIGQUERY_SOURCE_NAME:-bigquery-source}" \
    --allow-unauthenticated

if [ $? -ne 0 ]; then
    echo "ERROR: Cloud Run deployment failed"
    exit 1
fi

# Get the service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" \
    --format='value(status.url)')

echo "========================================"
echo "Deployment completed successfully!"
echo "========================================"
echo "Service URL: $SERVICE_URL"
echo ""
echo "Test the health endpoint:"
echo "  curl $SERVICE_URL/health"
echo ""
echo "View logs:"
echo "  gcloud run services logs read $SERVICE_NAME --region $REGION --limit 50"
echo ""
echo "Update service (reload tools.yaml):"
echo "  gcloud run services update $SERVICE_NAME --region $REGION"
echo "========================================"
