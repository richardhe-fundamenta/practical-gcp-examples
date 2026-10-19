# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He

output "mcp_server_url" {
  description = "Register this exact *.run.app URL in Gemini Enterprise (it is what makes Gemini Enterprise attach a Google ID token)."
  value       = "${google_cloud_run_v2_service.mcp.uri}/mcp"
}

output "agent_gateway" {
  description = "Egress Agent Gateway to bind to the Gemini Enterprise app."
  value       = "projects/${local.project_number}/locations/${var.gateway_region}/agentGateways/${google_network_services_agent_gateway.egress.name}"
}

output "entra_secrets" {
  description = "Secret Manager secrets to fill with the Entra app registration values."
  value       = { for k, s in google_secret_manager_secret.entra : k => s.secret_id }
}

output "image_repo" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "audit_dataset" {
  value = google_logging_linked_dataset.audit.link_id
}
