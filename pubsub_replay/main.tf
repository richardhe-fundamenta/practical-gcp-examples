# main.tf

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "europe-west2"
}

data "google_project" "project" {
  project_id = var.project_id
}

# Enable required APIs
resource "google_project_service" "txn_services" {
  for_each = toset([
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com"  # Required for Cloud Functions 2nd gen
  ])
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# Create the PubSub topic
resource "google_pubsub_topic" "txn_events" {
  project = var.project_id
  name    = "transaction-state-events"
}

# Create the trigger topic for the Cloud Function
resource "google_pubsub_topic" "function_trigger" {
  project = var.project_id
  name    = "txn-function-trigger"
}

# Allow Pub/Sub Trigger to invoke the Cloud Function
resource "google_cloud_run_service_iam_member" "pubsub_invoker" {
  project  = var.project_id
  location = var.region
  service  = google_cloudfunctions2_function.txn_pull_subscriber.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Service account for Pull Cloud Function
resource "google_service_account" "txn_pull_function_account" {
  project      = var.project_id
  account_id   = "txn-pull-function-sa"
  display_name = "Transaction Pull Function Service Account"
}

# Pull subscription
resource "google_pubsub_subscription" "txn_pull_subscription" {
  project = var.project_id
  name    = "transaction-state-events-pull"
  topic = google_pubsub_topic.txn_events.name

  # Acknowledge deadline of 60 seconds
  ack_deadline_seconds = 60

  # Expire messages after 7 days
  message_retention_duration = "604800s"

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# IAM binding for the pull subscription
resource "google_pubsub_subscription_iam_member" "txn_pull_function_subscriber" {
  project      = var.project_id
  subscription = google_pubsub_subscription.txn_pull_subscription.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.txn_pull_function_account.email}"
}

# Cloud Storage bucket for function source code
resource "google_storage_bucket" "txn_function_bucket" {
  project                     = var.project_id
  name                        = "${var.project_id}-txn-function-source"
  location                    = var.region
  uniform_bucket_level_access = true
}

# Zip the function source code including requirements.txt
data "archive_file" "txn_pull_function_zip" {
  type        = "zip"
  output_path = "/tmp/txn_pull_function.zip"

  source {
    content = file("${path.module}/pull_function/main.py")
    filename = "main.py"
  }

  source {
    content = file("${path.module}/pull_function/requirements.txt")
    filename = "requirements.txt"
  }
}

# Upload the source code to GCS
resource "google_storage_bucket_object" "txn_pull_function_source" {
  name   = "txn-pull-function-${data.archive_file.txn_pull_function_zip.output_md5}.zip"
  bucket = google_storage_bucket.txn_function_bucket.name
  source = data.archive_file.txn_pull_function_zip.output_path
}

# Cloud Function v2
resource "google_cloudfunctions2_function" "txn_pull_subscriber" {
  project  = var.project_id
  name     = "txn-state-pull-subscriber"
  location = var.region

  build_config {
    runtime     = "python310"
    entry_point = "process_messages"
    source {
      storage_source {
        bucket = google_storage_bucket.txn_function_bucket.name
        object = google_storage_bucket_object.txn_pull_function_source.name
      }
    }
  }

  service_config {
    max_instance_count    = 3
    min_instance_count    = 0
    available_memory      = "256M"
    timeout_seconds       = 540
    service_account_email = google_service_account.txn_pull_function_account.email
    environment_variables = {
      PROJECT_ID      = var.project_id
      SUBSCRIPTION_ID = google_pubsub_subscription.txn_pull_subscription.name
    }
    ingress_settings = "ALLOW_INTERNAL_ONLY"
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = "projects/${var.project_id}/topics/txn-function-trigger"
    retry_policy   = "RETRY_POLICY_RETRY"
  }

  depends_on = [
    google_pubsub_subscription_iam_member.txn_pull_function_subscriber,
    google_pubsub_topic.function_trigger
  ]
}



