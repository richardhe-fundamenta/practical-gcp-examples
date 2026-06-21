resource "google_compute_network" "agent" {
  name                    = "agent-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id
}

resource "google_compute_subnetwork" "agent" {
  name          = "agent-subnet"
  region        = var.region
  network       = google_compute_network.agent.id
  ip_cidr_range = "10.10.0.0/24"
  project       = var.project_id
}
