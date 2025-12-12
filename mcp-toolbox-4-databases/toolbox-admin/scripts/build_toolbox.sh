#!/bin/bash
# Mirror official MCP Toolbox image to your Artifact Registry (optional)
# By default, Terraform uses the official image directly

set -e

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"

if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID not set"
    exit 1
fi

REGION="${REGION:-us-central1}"
REPOSITORY="${REPOSITORY:-mcp-toolbox}"
TOOLBOX_VERSION="${TOOLBOX_VERSION:-0.22.0}"
OFFICIAL_IMAGE="us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:$TOOLBOX_VERSION"

echo "Mirroring MCP Toolbox image..."
echo "Source:      $OFFICIAL_IMAGE"
echo "Destination: $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/toolbox:$TOOLBOX_VERSION"
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

# Pull official image
echo "Pulling official image..."
docker pull "$OFFICIAL_IMAGE"

# Tag for your registry
TARGET_IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/toolbox:$TOOLBOX_VERSION"
docker tag "$OFFICIAL_IMAGE" "$TARGET_IMAGE"
docker tag "$OFFICIAL_IMAGE" "$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/toolbox:latest"

# Configure Docker auth for Artifact Registry
gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet

# Push to your registry
echo "Pushing to your Artifact Registry..."
docker push "$TARGET_IMAGE"
docker push "$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/toolbox:latest"

echo ""
echo "✓ Toolbox image mirrored successfully"
echo "  $TARGET_IMAGE"
echo ""
echo "Note: You can use either the official image or your mirrored version in Terraform"
