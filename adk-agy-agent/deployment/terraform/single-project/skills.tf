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

# Dynamic-skills infrastructure: a GCS bucket whose entire contents are mounted
# into the managed agent's sandbox. Skills added to the bucket appear on the next
# interaction with no further calls (verified on-demand mounting), so there is NO
# event-driven sync — just this bucket, an IAM grant, and a one-off bootstrap.

variable "skills_bucket_name" {
  type        = string
  description = "Skills bucket name. Defaults to <project_id>-agy-skills."
  default     = ""
}

variable "managed_agent_id" {
  type        = string
  description = "Fixed ID of the managed skills agent."
  default     = "agy-skill-agent"
}

variable "managed_agent_location" {
  type        = string
  description = "Agents/Interactions API location (must be 'global')."
  default     = "global"
}

variable "managed_agent_network_allowlist" {
  type = string
  # NOTE: the Managed Agents preview only accepts "*" when a GCS source is mounted
  # (specific domains are rejected). Tighten when the platform supports it.
  description = "Comma-separated sandbox egress allowlist (platform currently only accepts '*')."
  default     = "*"
}

locals {
  skills_bucket = var.skills_bucket_name != "" ? var.skills_bucket_name : "${var.project_id}-agy-skills"
}

# Skills bucket. Layout: skills/<name>/SKILL.md (+ optional files).
# NOTE: if this bucket already exists, import it first:
#   terraform import google_storage_bucket.skills <bucket-name>
resource "google_storage_bucket" "skills" {
  name                        = local.skills_bucket
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true

  depends_on = [google_project_service.services]
}

data "google_project" "this" {
  project_id = var.project_id
}

# The Agent Platform service identity reads mounted skill files on demand.
# If it does not exist yet on a fresh project, create it once:
#   gcloud beta services identity create --service=aiplatform.googleapis.com --project=<id>
resource "google_storage_bucket_iam_member" "agent_platform_skills_reader" {
  bucket = google_storage_bucket.skills.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
}

# One-off, idempotent bootstrap of the managed agent (whole-bucket mount).
# Re-runs only when the bucket, agent id, or bootstrap script changes.
resource "null_resource" "bootstrap_managed_agent" {
  triggers = {
    bucket   = google_storage_bucket.skills.name
    agent_id = var.managed_agent_id
    script   = filemd5("${path.module}/../../../tools/bootstrap_managed_agent.py")
  }

  provisioner "local-exec" {
    command     = "uv run python tools/bootstrap_managed_agent.py"
    working_dir = "${path.module}/../../.."
    environment = {
      GOOGLE_CLOUD_PROJECT            = var.project_id
      MANAGED_AGENT_LOCATION          = var.managed_agent_location
      SKILLS_BUCKET                   = google_storage_bucket.skills.name
      MANAGED_AGENT_ID                = var.managed_agent_id
      MANAGED_AGENT_NETWORK_ALLOWLIST = var.managed_agent_network_allowlist
    }
  }

  depends_on = [google_storage_bucket_iam_member.agent_platform_skills_reader]
}

output "skills_bucket" {
  value       = google_storage_bucket.skills.name
  description = "GCS bucket where skills are uploaded (skills/<name>/SKILL.md)."
}

output "managed_agent_id" {
  value       = var.managed_agent_id
  description = "ID of the managed skills agent."
}
