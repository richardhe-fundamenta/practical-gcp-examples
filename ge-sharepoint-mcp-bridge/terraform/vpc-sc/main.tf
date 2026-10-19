# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He

# ------------------------------------------------------------------------------
# VPC Service Controls perimeter in DRY-RUN mode (separate root module).
#
# Perimeters live in the organization's access policy, so an Access Context
# Manager admin applies this, not the project owner. Dry run only logs
# violations (cloudaudit.googleapis.com/policy, dryRun=true); nothing is
# blocked. Turn findings into ingress/egress rules or access levels with
# scripts/vpcsc_dashboard.py, then promote spec -> status to enforce.
# ------------------------------------------------------------------------------
terraform {
  required_version = ">= 1.6"
  # Bucket and prefix are passed at init: terraform init -backend-config=bucket=... -backend-config=prefix=...
  backend "gcs" {}
  required_providers {
    google = { source = "hashicorp/google", version = ">= 7.0" }
  }
}

variable "project_id" {
  description = "Project running the bridge."
  type        = string
}

variable "access_policy" {
  description = "Numeric access policy ID: gcloud access-context-manager policies list --organization=ORG_ID"
  type        = string
}

variable "extra_project_ids" {
  description = "Other projects to place in the same perimeter."
  type        = list(string)
  default     = []
}

variable "perimeter_name" {
  type    = string
  default = "spmcp_bridge"
}

variable "restricted_services" {
  type = list(string)
  default = [
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "cloudbuild.googleapis.com",
    "discoveryengine.googleapis.com",
    "logging.googleapis.com",
    "networksecurity.googleapis.com",
    "networkservices.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
  ]
}

provider "google" {
  billing_project       = var.project_id
  user_project_override = true
}

data "google_project" "members" {
  for_each   = toset(concat([var.project_id], var.extra_project_ids))
  project_id = each.value
}

resource "google_access_context_manager_service_perimeter" "bridge" {
  parent = "accessPolicies/${var.access_policy}"
  name   = "accessPolicies/${var.access_policy}/servicePerimeters/${var.perimeter_name}"
  title  = var.perimeter_name

  use_explicit_dry_run_spec = true
  spec {
    resources           = [for p in data.google_project.members : "projects/${p.number}"]
    restricted_services = var.restricted_services
  }
}
