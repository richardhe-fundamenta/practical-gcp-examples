# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He

terraform {
  required_version = ">= 1.6"
  # Bucket and prefix are passed at init: terraform init -backend-config=bucket=... -backend-config=prefix=...
  backend "gcs" {}
  required_providers {
    google      = { source = "hashicorp/google", version = ">= 7.0" }
    google-beta = { source = "hashicorp/google-beta", version = ">= 7.0" }
  }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

provider "google-beta" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}
