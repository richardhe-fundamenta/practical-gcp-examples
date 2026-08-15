terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    # google-beta only for google_project_service_identity (IAP's service agent).
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
  }

  # Remote state in GCS. The state bucket must already exist (see infra/README-style
  # bootstrap in the project README). Supply it at init time so nothing is hardcoded:
  #   terraform init -backend-config="bucket=<state-bucket>"
  backend "gcs" {
    prefix = "script-to-video-generator"
  }
}

provider "google" {
  project = var.infra_project
  region  = var.region
}

provider "google-beta" {
  project = var.infra_project
  region  = var.region
}
