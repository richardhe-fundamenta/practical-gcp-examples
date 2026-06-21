terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 7.37.0, < 8.0.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 7.37.0, < 8.0.0"
    }
  }
  backend "gcs" {
    bucket = "rocketech-de-pgcp-sandbox-tfstate"
    prefix = "gke-sandbox"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
