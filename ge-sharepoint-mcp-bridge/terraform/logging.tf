# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He

# Audit trail: one event per tool call -> dedicated bucket -> BigQuery.
# Log Analytics only indexes logs written after it is enabled, so it is on from day one.
resource "google_logging_project_bucket_config" "audit" {
  project          = var.project_id
  location         = var.region
  bucket_id        = "${var.prefix}-audit"
  retention_days   = var.audit_retention_days
  enable_analytics = true
  depends_on       = [google_project_service.apis]
}

resource "google_logging_linked_dataset" "audit" {
  link_id = "${replace(var.prefix, "-", "_")}_audit"
  bucket  = google_logging_project_bucket_config.audit.id
}

resource "google_logging_project_sink" "audit" {
  name                   = "${var.prefix}-audit"
  destination            = "logging.googleapis.com/${google_logging_project_bucket_config.audit.id}"
  filter                 = "jsonPayload.event_type=\"MCP_BRIDGE_AUDIT\" AND resource.labels.service_name=\"${var.service_name}\""
  unique_writer_identity = true
}
