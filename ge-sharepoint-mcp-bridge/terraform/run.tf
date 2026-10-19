# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He

resource "google_artifact_registry_repository" "images" {
  repository_id = "${var.prefix}-images"
  location      = var.region
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# ------------------------------------------------------------------------------
# MCP server
#   internal ingress   -> unreachable from the internet
#   IAM invoker check  -> only the Gemini Enterprise service agent may call it
#   ALL_TRAFFIC egress -> leaves only through Cloud NAT
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "mcp" {
  name                = var.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = false

  template {
    service_account = google_service_account.runtime.email

    scaling {
      max_instance_count = 5
    }

    vpc_access {
      egress = "ALL_TRAFFIC"
      network_interfaces {
        network    = google_compute_network.vpc.id
        subnetwork = google_compute_subnetwork.run.id
      }
    }

    containers {
      # Placeholder until Cloud Build rolls out the real image.
      image = "us-docker.pkg.dev/cloudrun/container/hello"
      ports {
        container_port = 8080
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "ALLOW_ANONYMOUS_LINKS"
        value = tostring(var.allow_anonymous_links)
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_compute_router_nat.nat]
}

resource "google_cloud_run_v2_service_iam_member" "invokers" {
  for_each   = toset(concat(["serviceAccount:${local.discovery_engine_sa}"], var.extra_invokers))
  name       = google_cloud_run_v2_service.mcp.name
  location   = var.region
  role       = "roles/run.invoker"
  member     = each.value
  depends_on = [google_project_service_identity.agents]
}

# "Refresh actions" in Gemini Enterprise reads the service before listing tools.
resource "google_cloud_run_v2_service_iam_member" "discovery_engine_viewer" {
  name       = google_cloud_run_v2_service.mcp.name
  location   = var.region
  role       = "roles/run.viewer"
  member     = "serviceAccount:${local.discovery_engine_sa}"
  depends_on = [google_project_service_identity.agents]
}

# Cloud Build (default compute SA) pushes images and rolls out new revisions.
resource "google_artifact_registry_repository_iam_member" "build_push" {
  repository = google_artifact_registry_repository.images.name
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${local.build_sa}"
}

resource "google_cloud_run_v2_service_iam_member" "build_deploy" {
  name     = google_cloud_run_v2_service.mcp.name
  location = var.region
  role     = "roles/run.developer"
  member   = "serviceAccount:${local.build_sa}"
}

resource "google_service_account_iam_member" "build_act_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.build_sa}"
}
