# Schema evidence (verified via `terraform providers schema -json` 2026-06-20):
# - addons_config.agent_sandbox_config.enabled = true  (enable_agent_sandbox does NOT exist)
# - control_plane_endpoints_config.dns_endpoint_config.allow_external_traffic = bool
# - control_plane_endpoints_config.dns_endpoint_config.endpoint (computed FQDN)
# - control_plane_endpoints_config.ip_endpoints_config.enabled = bool  (note: plural "endpoints")
# - private_cluster_config.enable_private_endpoint governs IP-endpoint default; removed here
#   because ip_endpoints_config.enabled=false is the authoritative control in the new block.

resource "google_container_cluster" "agent" {
  provider            = google-beta
  name                = "agent-sandbox"
  location            = var.region
  project             = var.project_id
  enable_autopilot    = true
  network             = google_compute_network.agent.id
  subnetwork          = google_compute_subnetwork.agent.id
  min_master_version  = "1.35.2-gke.1269000"
  deletion_protection = false
  depends_on          = [google_project_service.services]

  addons_config {
    agent_sandbox_config {
      enabled = true
    }
  }

  # DNS-based control-plane endpoint (IAM-gated, publicly-trusted TLS).
  # Nodes remain private (enable_private_nodes = true).
  # IP endpoint disabled — all access goes through the DNS endpoint.
  control_plane_endpoints_config {
    dns_endpoint_config {
      allow_external_traffic = true
    }
    ip_endpoints_config {
      enabled = false
    }
  }

  private_cluster_config {
    enable_private_nodes   = true
    master_ipv4_cidr_block = "172.16.0.0/28"
  }

  ip_allocation_policy {}
}
