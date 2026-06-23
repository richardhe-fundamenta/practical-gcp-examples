# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


resource "google_cloud_run_v2_service" "app" {
  name                = var.project_name
  location            = var.region
  project             = var.project_id
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  labels = {
    "created-by" = "adk"
  }

  template {
    vpc_access {
      network_interfaces {
        # Cloud Run wants a network/subnet NAME, not the full self_link URL.
        network    = basename(data.terraform_remote_state.platform.outputs.network_self_link)
        subnetwork = basename(data.terraform_remote_state.platform.outputs.subnet_self_link)
      }
      # PRIVATE_RANGES_ONLY routes only RFC1918 ranges (172.16.0.0/28 control plane,
      # 10.10.0.0/24 router) through VPC; internet & Vertex AI egress normally, no Cloud NAT needed.
      egress = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"
      env {
        name  = "APP_URL"
        value = "https://${var.project_name}-${data.google_project.project.number}.${var.region}.run.app"
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "4Gi"
        }
      }

      env {
        name  = "LOGS_BUCKET_NAME"
        value = google_storage_bucket.logs_data_bucket.name
      }

      # SA email used to sign V4 GCS URLs (A2UI chart hosting) via IAM signBlob.
      env {
        name  = "SIGNING_SERVICE_ACCOUNT"
        value = google_service_account.app_sa.email
      }

      # Dedicated bucket for hosted A2UI chart images (auto-expiring).
      env {
        name  = "CHART_BUCKET"
        value = google_storage_bucket.a2ui_outputs_bucket.name
      }

      # Dedicated bucket for user uploads, re-hydrated into the sandbox across conversation turns.
      env {
        name  = "UPLOADS_BUCKET"
        value = google_storage_bucket.uploads_bucket.name
      }

      env {
        name  = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
        value = "NO_CONTENT"
      }

      # Sandbox connectivity env vars
      env {
        name  = "SANDBOX_TEMPLATE"
        value = "python-sandbox-template"
      }

      env {
        name  = "SANDBOX_NAMESPACE"
        value = "default"
      }

      # Bare FQDN (no https://) — kube_auth prepends the scheme.
      env {
        name  = "GKE_ENDPOINT"
        value = data.terraform_remote_state.platform.outputs.gke_dns_endpoint
      }

      # SANDBOX_API_URL: set at apply time once the k8s-agent-sandbox Router service
      # is deployed and its internal LoadBalancer address is known (Task 7).
      env {
        name  = "SANDBOX_API_URL"
        value = var.sandbox_api_url
      }
    }

    service_account                  = google_service_account.app_sa.email
    max_instance_request_concurrency = 20

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    session_affinity = true
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  # This lifecycle block prevents Terraform from overwriting the container image when it's
  # updated by Cloud Run deployments outside of Terraform (e.g., deployment/deploy-image.sh).
  # `client`/`client_version` are metadata gcloud stamps on every deploy — ignore them so plans
  # stay quiet. (We deliberately do NOT ignore build_config / env / scaling: those only drift
  # when a source-based `agents-cli deploy` sneaks in, and we want that to surface.)
  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  # Make dependencies conditional to avoid errors.
  depends_on = [
    resource.google_project_service.services,
  ]
}
