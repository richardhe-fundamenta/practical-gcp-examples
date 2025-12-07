# Cloud Run Deployment Guide

This project deploys **two separate Cloud Run services**:

1. **Admin UI** - FastAPI web application for managing queries
2. **MCP Toolbox** - Query execution server using the official pre-built image

## Architecture Overview

```
┌─────────────────┐         ┌──────────────────┐
│   Admin UI      │         │  MCP Toolbox     │
│   (FastAPI)     │────────▶│  (Official Image)│
│   Port 8080     │         │  Port 8080       │
└─────────────────┘         └──────────────────┘
        │                            │
        │                            │
        ▼                            ▼
   BigQuery                     tools.yaml
   Registry                  (from Secret Manager
                             or Cloud Storage)
```

## Prerequisites

- GCP Project with required APIs enabled:
  - Cloud Run API
  - BigQuery API
  - Secret Manager API (optional)
  - Cloud Storage API (optional)
- gcloud CLI configured
- Docker installed (for building admin UI image)
- Service account with appropriate permissions

## Deployment Steps

### 1. Build and Deploy Admin UI

#### Build the Docker image

```bash
cd admin_ui
docker build -t gcr.io/YOUR_PROJECT_ID/mcp-admin-ui:latest .
docker push gcr.io/YOUR_PROJECT_ID/mcp-admin-ui:latest
```

#### Deploy to Cloud Run

```bash
gcloud run deploy mcp-admin-ui \
  --image gcr.io/YOUR_PROJECT_ID/mcp-admin-ui:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=YOUR_PROJECT_ID,\
REGISTRY_DATASET=example_mcp_toolbox_4_dbs,\
REGISTRY_TABLE=query_registry,\
BIGQUERY_SOURCE_NAME=bigquery-source,\
TOOLS_FILE=/app/tools.yaml \
  --service-account YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10
```

### 2. Deploy MCP Toolbox (Official Pre-built Image)

#### Option A: Using tools.yaml from Secret Manager (Recommended)

1. Create the secret:
```bash
gcloud secrets create mcp-tools-yaml --data-file=tools.yaml
```

2. Grant access to the service account:
```bash
gcloud secrets add-iam-policy-binding mcp-tools-yaml \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

3. Deploy the toolbox:
```bash
gcloud run deploy mcp-toolbox \
  --image us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:0.22.0 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets /app/tools.yaml=mcp-tools-yaml:latest \
  --args="--tools-file=/app/tools.yaml","--address=0.0.0.0","--port=8080" \
  --service-account YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --memory 1Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10
```

#### Option B: Using tools.yaml from Cloud Storage

1. Upload to Cloud Storage:
```bash
gsutil cp tools.yaml gs://YOUR_BUCKET/tools.yaml
```

2. Mount the bucket and deploy:
```bash
gcloud run deploy mcp-toolbox \
  --image us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:0.22.0 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --execution-environment gen2 \
  --add-volume name=gcs,type=cloud-storage,bucket=YOUR_BUCKET \
  --add-volume-mount volume=gcs,mount-path=/mnt/gcs \
  --args="--tools-file=/mnt/gcs/tools.yaml","--address=0.0.0.0","--port=8080" \
  --service-account YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --memory 1Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10
```

## Service Account Permissions

Your service account needs the following roles:

```bash
# For Admin UI
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

# For MCP Toolbox
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

# If using Secret Manager
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# If using Cloud Storage
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

## Updating the Toolbox Configuration

### Workflow

1. **Update queries** via Admin UI web interface
   - Add/edit/delete queries in the BigQuery registry

2. **Regenerate tools.yaml**
   - Click "Submit All Changes" in the Admin UI
   - Or call the API endpoint: `POST /api/reload`

3. **Update the toolbox**
   - **If using Secret Manager**: Update the secret
     ```bash
     gcloud secrets versions add mcp-tools-yaml --data-file=tools.yaml
     ```
     Cloud Run will automatically pick up the new version

   - **If using Cloud Storage**: Upload the new file
     ```bash
     gsutil cp tools.yaml gs://YOUR_BUCKET/tools.yaml
     ```
     The toolbox will reload the configuration automatically

## Testing

### Test Admin UI
```bash
curl https://mcp-admin-ui-HASH-uc.a.run.app/health
# Expected: {"status":"healthy","service":"admin-ui"}
```

### Test MCP Toolbox
```bash
curl https://mcp-toolbox-HASH-uc.a.run.app/health
# Expected: {"status":"ok"}
```

## Monitoring

View logs for each service:

```bash
# Admin UI logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=mcp-admin-ui" --limit 50 --format json

# Toolbox logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=mcp-toolbox" --limit 50 --format json
```

## Cost Optimization

- **Admin UI**: Set `--min-instances=0` (default) to scale to zero when not in use
- **MCP Toolbox**: Consider `--min-instances=1` if you need fast response times
- Use `--cpu-throttling` for cost savings on low-traffic services
- Set appropriate `--concurrency` values based on workload

## Security Best Practices

1. Use **authentication** for production:
   ```bash
   --no-allow-unauthenticated
   ```

2. Use **VPC connector** for private BigQuery access

3. Implement rate limiting and request validation

4. Use **Cloud Armor** for DDoS protection

5. Enable **Binary Authorization** for container image verification
