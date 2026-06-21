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

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
}

resource "google_storage_bucket" "logs_data_bucket" {
  name                        = "${var.project_id}-${var.project_name}-logs"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true

  depends_on = [resource.google_project_service.services]
}

# Dedicated bucket for user uploads, re-hydrated into the sandbox across turns of a conversation
# (session-uploads/<conversation_id>/...). Kept separate from logs/artifacts so its retention and
# access are easy to reason about. Objects auto-delete after a week (covers a conversation's life).
resource "google_storage_bucket" "uploads_bucket" {
  name                        = "${var.project_id}-${var.project_name}-uploads"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [resource.google_project_service.services]
}

# Dedicated bucket for hosted A2UI chart images (referenced via short-lived signed URLs).
# Objects auto-delete after 1 day (lifecycle granularity is days); the signed URL itself only
# grants access for SIGNED_URL_TTL_MINUTES (default 15 min), so real exposure is that window.
resource "google_storage_bucket" "a2ui_outputs_bucket" {
  name                        = "${var.project_id}-${var.project_name}-a2ui-outputs"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [resource.google_project_service.services]
}
