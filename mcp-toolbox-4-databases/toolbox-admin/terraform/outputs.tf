output "admin_ui_url" {
  description = "URL of the deployed Admin UI service"
  value       = google_cloud_run_v2_service.admin_ui.uri
}

output "toolbox_url" {
  description = "URL of the deployed MCP Toolbox service"
  value       = google_cloud_run_v2_service.toolbox.uri
}

output "admin_ui_service_account_email" {
  description = "Email of the Admin UI service account"
  value       = google_service_account.admin_ui.email
}

output "toolbox_service_account_email" {
  description = "Email of the Toolbox service account"
  value       = google_service_account.toolbox.email
}

output "tools_yaml_secret_id" {
  description = "Secret Manager secret ID for tools.yaml"
  value       = google_secret_manager_secret.tools_yaml.secret_id
}

output "admin_ui_service_name" {
  description = "Name of the Admin UI Cloud Run service"
  value       = google_cloud_run_v2_service.admin_ui.name
}

output "toolbox_service_name" {
  description = "Name of the Toolbox Cloud Run service"
  value       = google_cloud_run_v2_service.toolbox.name
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository name"
  value       = google_artifact_registry_repository.docker.name
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}
