# Enable required APIs
resource "google_project_service" "cloud_run" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquery" {
  service            = "bigquery.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "secret_manager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_build" {
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifact_registry" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

# Create Artifact Registry repository for Docker images
resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = var.artifact_registry_repository
  description   = "Docker repository for MCP Toolbox images"
  format        = "DOCKER"

  depends_on = [google_project_service.artifact_registry]
}

# Create service account for Admin UI
resource "google_service_account" "admin_ui" {
  account_id   = var.admin_ui_service_account_name
  display_name = "MCP Admin UI Service Account"
  description  = "Service account for MCP Admin UI Cloud Run service with BigQuery edit access"
}

# Create service account for MCP Toolbox
resource "google_service_account" "toolbox" {
  account_id   = var.toolbox_service_account_name
  display_name = "MCP Toolbox Service Account"
  description  = "Service account for MCP Toolbox Cloud Run service with BigQuery read-only access"
}

# IAM roles for Admin UI service account (read/write access to BigQuery and Secret Manager)
resource "google_project_iam_member" "admin_ui_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.admin_ui.email}"
}

resource "google_project_iam_member" "admin_ui_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.admin_ui.email}"
}

resource "google_project_iam_member" "admin_ui_secret_admin" {
  project = var.project_id
  role    = "roles/secretmanager.secretVersionAdder"
  member  = "serviceAccount:${google_service_account.admin_ui.email}"
}

# IAM roles for Toolbox service account (read-only access to BigQuery)
resource "google_project_iam_member" "toolbox_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.toolbox.email}"
}

resource "google_project_iam_member" "toolbox_bigquery_data_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.toolbox.email}"
}

# Secret Manager access for Toolbox service account
resource "google_project_iam_member" "toolbox_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.toolbox.email}"
}

# Create Secret Manager secret for tools.yaml
resource "google_secret_manager_secret" "tools_yaml" {
  secret_id = var.tools_yaml_secret_name

  replication {
    auto {}
  }

  depends_on = [google_project_service.secret_manager]
}

# Add the tools.yaml content to the secret
resource "google_secret_manager_secret_version" "tools_yaml" {
  secret      = google_secret_manager_secret.tools_yaml.id
  secret_data = var.tools_yaml_content
}

# Deploy Admin UI Cloud Run service
resource "google_cloud_run_v2_service" "admin_ui" {
  name     = var.admin_ui_service_name
  location = var.region

  template {
    service_account = google_service_account.admin_ui.email

    containers {
      image = var.admin_ui_image

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "REGISTRY_DATASET"
        value = var.registry_dataset
      }

      env {
        name  = "REGISTRY_TABLE"
        value = var.registry_table
      }

      env {
        name  = "BIGQUERY_SOURCE_NAME"
        value = var.bigquery_source_name
      }

      env {
        name  = "TOOLS_FILE"
        value = var.tools_file_path
      }

      env {
        name  = "DEBUG_MODE"
        value = "false"
      }

      env {
        name  = "SECRET_NAME"
        value = var.tools_yaml_secret_name
      }

      resources {
        limits = {
          cpu    = var.admin_ui_cpu
          memory = var.admin_ui_memory
        }
      }
    }

    timeout         = "${var.admin_ui_timeout}s"
    max_instance_count = var.admin_ui_max_instances
  }

  depends_on = [google_project_service.cloud_run]
}

# Deploy MCP Toolbox Cloud Run service
resource "google_cloud_run_v2_service" "toolbox" {
  name     = var.toolbox_service_name
  location = var.region

  template {
    service_account = google_service_account.toolbox.email

    containers {
      image = var.toolbox_image

      args = [
        "--tools-file=${var.tools_file_path}",
        "--address=${var.toolbox_address}",
        "--port=${var.toolbox_port}"
      ]

      volume_mounts {
        name       = "tools-yaml"
        mount_path = var.tools_file_path
      }

      resources {
        limits = {
          cpu    = var.toolbox_cpu
          memory = var.toolbox_memory
        }
      }
    }

    volumes {
      name = "tools-yaml"
      secret {
        secret       = google_secret_manager_secret.tools_yaml.secret_id
        default_mode = 0444
        items {
          version = "latest"
          path    = basename(var.tools_file_path)
        }
      }
    }

    timeout         = "${var.toolbox_timeout}s"
    max_instance_count = var.toolbox_max_instances
  }

  depends_on = [
    google_project_service.cloud_run,
    google_secret_manager_secret_version.tools_yaml
  ]
}

# IAM policy to allow unauthenticated access to Admin UI
resource "google_cloud_run_v2_service_iam_member" "admin_ui_noauth" {
  count = var.allow_unauthenticated ? 1 : 0

  location = google_cloud_run_v2_service.admin_ui.location
  name     = google_cloud_run_v2_service.admin_ui.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# IAM policy to allow unauthenticated access to Toolbox
resource "google_cloud_run_v2_service_iam_member" "toolbox_noauth" {
  count = var.allow_unauthenticated ? 1 : 0

  location = google_cloud_run_v2_service.toolbox.location
  name     = google_cloud_run_v2_service.toolbox.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
