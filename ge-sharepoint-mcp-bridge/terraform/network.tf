# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He

resource "google_compute_network" "vpc" {
  name                    = "${var.prefix}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

# Cloud Run sends all outbound traffic into this subnet (Direct VPC egress).
resource "google_compute_subnetwork" "run" {
  name                     = "${var.prefix}-run-${var.region}"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = var.run_subnet_cidr
  private_ip_google_access = true
}

# The Agent Gateway lands in the VPC through a PSC network attachment on this subnet.
resource "google_compute_subnetwork" "gateway" {
  name                     = "${var.prefix}-agw-${var.gateway_region}"
  region                   = var.gateway_region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = var.gateway_subnet_cidr
  private_ip_google_access = true
}

resource "google_compute_network_attachment" "gateway" {
  name                  = "${var.prefix}-agw-attachment"
  region                = var.gateway_region
  connection_preference = "ACCEPT_AUTOMATIC"
  subnetworks           = [google_compute_subnetwork.gateway.id]
}

# ------------------------------------------------------------------------------
# *.run.app -> PSC endpoint for Google APIs, so Cloud Run sees internal traffic
# ------------------------------------------------------------------------------
resource "google_compute_global_address" "psc" {
  name         = "${var.prefix}-psc-apis"
  address_type = "INTERNAL"
  purpose      = "PRIVATE_SERVICE_CONNECT"
  network      = google_compute_network.vpc.id
  address      = var.psc_endpoint_ip
}

resource "google_compute_global_forwarding_rule" "psc" {
  # PSC endpoints for Google APIs need 1-20 lowercase letters and digits.
  name                  = substr(replace("${var.prefix}apis", "/[^a-z0-9]/", ""), 0, 20)
  target                = "all-apis"
  network               = google_compute_network.vpc.id
  ip_address            = google_compute_global_address.psc.id
  load_balancing_scheme = ""
}

resource "google_dns_managed_zone" "run_app" {
  name       = "${var.prefix}-run-app"
  dns_name   = "run.app."
  visibility = "private"
  private_visibility_config {
    networks {
      network_url = google_compute_network.vpc.id
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_dns_record_set" "run_app" {
  for_each     = toset(["run.app.", "*.run.app."])
  name         = each.value
  managed_zone = google_dns_managed_zone.run_app.name
  type         = "A"
  ttl          = 60
  rrdatas      = [var.psc_endpoint_ip]
}

# Gateway attachment subnet -> PSC endpoint on 443 only.
resource "google_compute_firewall" "gateway_to_psc" {
  name               = "${var.prefix}-agw-to-psc"
  network            = google_compute_network.vpc.id
  direction          = "INGRESS"
  source_ranges      = [var.gateway_subnet_cidr]
  destination_ranges = ["${var.psc_endpoint_ip}/32"]
  allow {
    protocol = "tcp"
    ports    = ["443"]
  }
  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

# ------------------------------------------------------------------------------
# Outbound internet for Cloud Run only (Microsoft Graph, Entra)
# ------------------------------------------------------------------------------
resource "google_compute_router" "nat" {
  name    = "${var.prefix}-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.prefix}-nat"
  router                             = google_compute_router.nat.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"
  subnetwork {
    name                    = google_compute_subnetwork.run.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
