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
  - Secret Manager API
- gcloud CLI configured
- Docker installed (for building admin UI image)
- Service account with appropriate permissions

## Deployment Steps

### 1. Build Docker Images

Build the Admin UI:
```bash
./scripts/build_admin_ui.sh
```

Optionally mirror the official Toolbox image to your Artifact Registry:
```bash
./scripts/build_toolbox.sh
```

Note: The Toolbox uses the official pre-built image by default. Only run `build_toolbox.sh` if you want to mirror it to your own registry.

### 2. Deploy with Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
- Set `project_id`
- Set `admin_ui_image` (output from build_admin_ui.sh)
- Add `tools_yaml_content`

Deploy:
```bash
terraform init
terraform apply
```

### 3. Verify Deployment

```bash
terraform output admin_ui_url
terraform output toolbox_url
```

## Updating the Toolbox Configuration

### Automated Workflow (Production)

The Admin UI automatically writes tools.yaml directly to Secret Manager:

1. **Update queries** via Admin UI web interface
   - Add/edit/delete queries in the BigQuery registry

2. **Regenerate tools.yaml**
   - Click "Submit All Changes" in the Admin UI
   - Or call the API endpoint: `POST /api/reload`
   - The Admin UI writes the new tools.yaml directly to Secret Manager

3. **Toolbox picks up changes automatically**
   - Cloud Run automatically uses the latest secret version
   - No manual secret updates needed!

### Manual Workflow (If Needed)

If you need to manually update the secret:
```bash
gcloud secrets versions add mcp-tools-yaml --data-file=tools.yaml
```

### Debug Mode (Local Development)

For local development, set `DEBUG_MODE=true`:
- The Admin UI will write tools.yaml to a local file instead of Secret Manager
- Useful for testing without GCP credentials
- Set in your `.env` file: `DEBUG_MODE=true`

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