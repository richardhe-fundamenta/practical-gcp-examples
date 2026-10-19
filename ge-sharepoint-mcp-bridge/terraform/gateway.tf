# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He

# ------------------------------------------------------------------------------
# Egress Agent Gateway: carries connector traffic from Gemini Enterprise into
# the VPC (PSC attachment) and resolves run.app with the VPC's private zone.
# ------------------------------------------------------------------------------
resource "google_network_services_agent_gateway" "egress" {
  name     = "${var.prefix}-egress-gateway"
  location = var.gateway_region

  google_managed {
    governed_access_path = "AGENT_TO_ANYWHERE"
  }

  network_config {
    egress {
      network_attachment = google_compute_network_attachment.gateway.id
    }
    dns_peering_config {
      domains        = ["run.app."]
      target_project = var.project_id
      target_network = google_compute_network.vpc.id
    }
  }

  registries = ["//agentregistry.googleapis.com/projects/${var.project_id}/locations/${var.gateway_region}"]

  depends_on = [
    google_project_iam_member.egress_agents,
    google_project_iam_member.agent_gateway_service_agent,
    google_dns_record_set.run_app,
  ]
}

# Managed egress gateways deny everything until a policy allows it
# (symptom: HTTP 403 "Access denied", server: envoy, nothing in Cloud Run logs).
resource "google_network_security_authz_policy" "egress" {
  name           = "${var.prefix}-egress-allow"
  location       = var.gateway_region
  action         = "ALLOW"
  policy_profile = "REQUEST_AUTHZ"

  target {
    resources = [google_network_services_agent_gateway.egress.id]
  }

  http_rules {
    to {
      operations {
        paths {
          prefix = "/"
        }
      }
    }
  }
}
