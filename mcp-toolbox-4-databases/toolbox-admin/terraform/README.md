# Terraform Configuration for MCP Toolbox

This Terraform configuration deploys the MCP Toolbox infrastructure to Google Cloud Platform, including:

- Two Cloud Run services (Admin UI and MCP Toolbox)
- Two separate service accounts with least-privilege permissions:
  - Admin UI service account with BigQuery edit access
  - Toolbox service account with BigQuery read-only access
- Secret Manager secret for tools.yaml configuration
- Required GCP APIs enablement

## Prerequisites

1. **GCP Project**: A GCP project with billing enabled
2. **Terraform**: Install Terraform >= 1.0
3. **gcloud CLI**: Authenticated and configured
4. **Docker Image**: Build and push the Admin UI Docker image before deploying

## Quick Start

### 1. Build Docker Images

Build the Admin UI:
```bash
./scripts/build_admin_ui.sh
```

Optionally mirror the Toolbox image:
```bash
./scripts/build_toolbox.sh
```

### 2. Configure Variables

Copy the example tfvars file and fill in your values:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:
- `project_id`: Your GCP project ID
- `admin_ui_image`: The Docker image URL you pushed
- `tools_yaml_content`: Content of your tools.yaml file

### 3. Initialize Terraform

```bash
terraform init
```

### 4. Plan Deployment

```bash
terraform plan
```

### 5. Deploy

```bash
terraform apply
```

### 6. Get Service URLs

```bash
terraform output admin_ui_url
terraform output toolbox_url
```

## Configuration Variables

### Required Variables

| Variable | Description |
|----------|-------------|
| `project_id` | GCP Project ID |
| `admin_ui_image` | Docker image for Admin UI |
| `tools_yaml_content` | Content of the tools.yaml configuration file |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `region` | `us-central1` | GCP region for deployment |
| `admin_ui_service_name` | `mcp-admin-ui` | Cloud Run service name for Admin UI |
| `toolbox_service_name` | `mcp-toolbox` | Cloud Run service name for Toolbox |
| `toolbox_image` | Official toolbox image | Docker image for MCP Toolbox |
| `registry_dataset` | `example_mcp_toolbox_4_dbs` | BigQuery dataset name |
| `registry_table` | `query_registry` | BigQuery table name |
| `admin_ui_service_account_name` | `mcp-admin-ui-sa` | Admin UI service account name |
| `toolbox_service_account_name` | `mcp-toolbox-sa` | Toolbox service account name |
| `admin_ui_memory` | `512Mi` | Memory for Admin UI |
| `admin_ui_cpu` | `1` | CPU for Admin UI |
| `toolbox_memory` | `1Gi` | Memory for Toolbox |
| `toolbox_cpu` | `2` | CPU for Toolbox |
| `allow_unauthenticated` | `true` | Allow public access |

See `variables.tf` for the complete list of configurable variables.

## Updating tools.yaml

To update the tools.yaml configuration after deployment:

### Method 1: Using Terraform

1. Update the `tools_yaml_content` variable in your `terraform.tfvars`
2. Run `terraform apply`

### Method 2: Using gcloud CLI

```bash
gcloud secrets versions add mcp-tools-yaml --data-file=../tools.yaml
```

The Toolbox service will automatically pick up the new version.

## Testing

After deployment, test the services:

```bash
# Test Admin UI
curl $(terraform output -raw admin_ui_url)/health

# Test Toolbox
curl $(terraform output -raw toolbox_url)/health
```

## Monitoring

View logs for the services:

```bash
# Admin UI logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$(terraform output -raw admin_ui_service_name)" --limit 50

# Toolbox logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$(terraform output -raw toolbox_service_name)" --limit 50
```

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

## Outputs

| Output | Description |
|--------|-------------|
| `admin_ui_url` | URL of the Admin UI service |
| `toolbox_url` | URL of the Toolbox service |
| `admin_ui_service_account_email` | Email of the Admin UI service account |
| `toolbox_service_account_email` | Email of the Toolbox service account |
| `tools_yaml_secret_id` | Secret Manager secret ID |
| `admin_ui_service_name` | Name of Admin UI service |
| `toolbox_service_name` | Name of Toolbox service |

## Architecture

```
┌─────────────────┐         ┌──────────────────┐
│   Admin UI      │         │  MCP Toolbox     │
│   (Cloud Run)   │────────▶│  (Cloud Run)     │
│                 │         │                  │
└─────────────────┘         └──────────────────┘
        │                            │
        │                            │
        ▼                            ▼
   BigQuery                  Secret Manager
   Registry                  (tools.yaml)
```

## Security Considerations

### Least Privilege Access
This configuration implements security best practices with two separate service accounts:

**Admin UI Service Account:**
- `roles/bigquery.dataEditor` - Can read and write to BigQuery registry
- `roles/bigquery.jobUser` - Can run BigQuery queries
- `roles/secretmanager.secretVersionAdder` - Can write new versions to Secret Manager (for tools.yaml updates)

**Toolbox Service Account:**
- `roles/bigquery.dataViewer` - Read-only access to BigQuery data
- `roles/bigquery.jobUser` - Can run BigQuery queries (read operations only)
- `roles/secretmanager.secretAccessor` - Can read the tools.yaml secret

This separation ensures that:
- Only the Admin UI can modify the query registry and update tools.yaml
- The Toolbox has read-only access and cannot modify data or secrets
- Each service has only the minimum permissions needed

### Tools.yaml Management

The Admin UI writes the tools.yaml configuration directly to Secret Manager:
- When queries are updated via the Admin UI, clicking "Submit All Changes" triggers regeneration
- The new tools.yaml is written as a new version in Secret Manager
- Cloud Run automatically picks up the latest version
- No manual secret updates needed!

**Debug Mode:** For local development, set `DEBUG_MODE=true` to write tools.yaml to a local file instead of Secret Manager.

### Additional Security
- The `tools_yaml_content` variable is marked as sensitive to prevent exposure in logs
- By default, services allow unauthenticated access. Set `allow_unauthenticated = false` for authenticated-only access
- Consider using Cloud Armor for additional protection if exposing publicly
- Consider restricting ingress to specific IP ranges using Cloud Run's ingress settings

## Troubleshooting

### Image not found
Ensure you've built and pushed the Admin UI Docker image before running terraform.

### Permission denied
Make sure you have the necessary permissions in the GCP project:
- `roles/owner` or equivalent permissions to create resources
- `gcloud auth application-default login` to authenticate Terraform

### Service deployment fails
Check that all required APIs are enabled. Terraform will enable them, but it may take a few minutes.
