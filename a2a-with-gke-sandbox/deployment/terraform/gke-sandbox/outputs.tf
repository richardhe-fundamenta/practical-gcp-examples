output "network_self_link" {
  description = "Self-link of the agent VPC"
  value       = google_compute_network.agent.self_link
}

output "subnet_self_link" {
  description = "Self-link of the agent subnet"
  value       = google_compute_subnetwork.agent.self_link
}

output "gke_dns_endpoint" {
  description = "GKE cluster DNS endpoint FQDN"
  value       = google_container_cluster.agent.control_plane_endpoints_config[0].dns_endpoint_config[0].endpoint
}

output "cluster_name" {
  description = "GKE cluster name"
  value       = google_container_cluster.agent.name
}

output "cluster_location" {
  description = "GKE cluster location"
  value       = google_container_cluster.agent.location
}

output "project_id" {
  description = "Project ID"
  value       = var.project_id
}

output "region" {
  description = "Region"
  value       = var.region
}
