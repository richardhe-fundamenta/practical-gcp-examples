# psc.tf
# Configures the Private Service Connect (PSC) global address and forwarding rule for Google APIs

resource "google_compute_global_address" "psc_address" {
  name          = "psc-google-apis"
  project       = var.project_id
  address_type  = "INTERNAL"
  purpose       = "PRIVATE_SERVICE_CONNECT"
  network       = data.google_compute_network.vpc.id
  address       = "10.120.1.100"
}

resource "google_compute_global_forwarding_rule" "psc_forwarding_rule" {
  name                  = "pscgoogleapisfw"
  project               = var.project_id
  target                = "all-apis"
  network               = data.google_compute_network.vpc.id
  ip_address            = google_compute_global_address.psc_address.id
  load_balancing_scheme = ""
}
