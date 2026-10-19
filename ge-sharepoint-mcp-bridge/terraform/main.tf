# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He

data "google_project" "this" {}

locals {
  project_number = data.google_project.this.number

  # Google-managed service agents on the private egress path.
  discovery_engine_sa = "service-${local.project_number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
  agent_gateway_sa    = "service-${local.project_number}@gcp-sa-agentgateway.iam.gserviceaccount.com"
  dep_sa              = "service-${local.project_number}@gcp-sa-dep.iam.gserviceaccount.com"
  build_sa            = "${local.project_number}-compute@developer.gserviceaccount.com"

  entra_secrets = ["client-id", "client-secret", "tenant-id"]
}

resource "google_project_service" "apis" {
  for_each = toset([
    "agentregistry.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "discoveryengine.googleapis.com",
    "dns.googleapis.com",
    "logging.googleapis.com",
    "networksecurity.googleapis.com",
    "networkservices.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicedirectory.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_project_service_identity" "agents" {
  # networkservices creates the gcp-sa-agentgateway and gcp-sa-dep agents granted below
  provider   = google-beta
  for_each   = toset(["discoveryengine.googleapis.com", "agentregistry.googleapis.com", "networkservices.googleapis.com"])
  service    = each.value
  depends_on = [google_project_service.apis]
}

# ------------------------------------------------------------------------------
# Service agent roles for the private egress path
#   networkUser + dns.peer : the gateway attaches to the VPC and peers DNS
#   networkservices.admin  : Gemini Enterprise binds the gateway to its app
# ------------------------------------------------------------------------------
locals {
  egress_agent_roles = {
    for pair in setproduct(
      ["discoveryengine", "agentgateway", "dep"],
      ["roles/compute.networkUser", "roles/dns.peer"],
    ) : "${pair[0]}|${pair[1]}" => pair
  }
  agent_email = {
    discoveryengine = local.discovery_engine_sa
    agentgateway    = local.agent_gateway_sa
    dep             = local.dep_sa
  }
}

resource "google_project_iam_member" "egress_agents" {
  for_each   = local.egress_agent_roles
  project    = var.project_id
  role       = each.value[1]
  member     = "serviceAccount:${local.agent_email[each.value[0]]}"
  depends_on = [google_project_service_identity.agents]
}

resource "google_project_iam_member" "agent_gateway_service_agent" {
  project    = var.project_id
  role       = "roles/agentgateway.serviceAgent"
  member     = "serviceAccount:${local.agent_gateway_sa}"
  depends_on = [google_project_service_identity.agents]
}

resource "google_project_iam_member" "dep_usage" {
  project    = var.project_id
  role       = "roles/serviceusage.serviceUsageConsumer"
  member     = "serviceAccount:${local.dep_sa}"
  depends_on = [google_project_service_identity.agents]
}

resource "google_project_iam_member" "discovery_engine_netservices" {
  project    = var.project_id
  role       = "roles/networkservices.admin"
  member     = "serviceAccount:${local.discovery_engine_sa}"
  depends_on = [google_project_service_identity.agents]
}

# ------------------------------------------------------------------------------
# Runtime identity and Entra app credentials (values added out of band)
# ------------------------------------------------------------------------------
resource "google_service_account" "runtime" {
  account_id   = "${var.prefix}-runtime"
  display_name = "SharePoint MCP bridge runtime"
}

resource "google_project_iam_member" "runtime_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret" "entra" {
  for_each  = toset(local.entra_secrets)
  secret_id = "${var.prefix}-entra-${each.value}"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}
