#!/bin/bash
# Build Admin UI Docker image using Cloud Build

set -e

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"

if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID not set"
    exit 1
fi

REGION="${REGION:-us-central1}"
REPOSITORY="${REPOSITORY:-mcp-toolbox}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "Building Admin UI..."
echo "Project:    $PROJECT_ID"
echo "Repository: $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY"
echo "Tag:        $IMAGE_TAG"
echo ""

# Create Artifact Registry repository if needed
if ! gcloud artifacts repositories describe "$REPOSITORY" \
    --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    echo "Creating Artifact Registry repository..."
    gcloud artifacts repositories create "$REPOSITORY" \
        --repository-format=docker \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        --description="MCP Toolbox Docker images"
fi

# Build and push
gcloud builds submit \
    --config=admin_ui/cloudbuild.yaml \
    --substitutions="_REGION=$REGION,_REPOSITORY=$REPOSITORY,_IMAGE_NAME=admin-ui,_IMAGE_TAG=$IMAGE_TAG" \
    --project="$PROJECT_ID" \
    .

echo ""
echo "✓ Admin UI image built successfully"
echo "  $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/admin-ui:$IMAGE_TAG"
