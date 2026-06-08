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

# Skills are managed in the Skill Registry (regional, us-central1) — registered
# from the repo skills/ folder and mounted read-only into the managed agent. No
# GCS bucket: skills can't be modified or deleted at runtime.

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

variable "skills_location" {
  type        = string
  description = "Skill Registry location (regional: us-central1 | europe-west4 | us-east5)."
  default     = "us-central1"
}

variable "managed_agent_network_allowlist" {
  type = string
  # NOTE: the preview only accepts "*" when any skill is mounted (specific domains
  # are rejected). Configurable for when the platform supports domain allowlists.
  description = "Comma-separated sandbox egress allowlist (platform currently only accepts '*')."
  default     = "*"
}

# Project number is used by gemini_enterprise.tf (Discovery Engine SA).
data "google_project" "this" {
  project_id = var.project_id
}

# One-off, idempotent bootstrap: register the repo's skills/ folder into the Skill
# Registry, then reconcile the managed agent to mount them. Re-runs when the skills
# or the tool scripts change.
resource "null_resource" "bootstrap_managed_agent" {
  triggers = {
    agent_id  = var.managed_agent_id
    register  = filemd5("${path.module}/../../../tools/register_skills.py")
    bootstrap = filemd5("${path.module}/../../../tools/bootstrap_managed_agent.py")
    skills = sha1(join("", [
      for f in fileset("${path.module}/../../../skills", "**") :
      filemd5("${path.module}/../../../skills/${f}")
    ]))
  }

  provisioner "local-exec" {
    command     = "uv run python tools/register_skills.py && uv run python tools/bootstrap_managed_agent.py"
    working_dir = "${path.module}/../../.."
    environment = {
      GOOGLE_CLOUD_PROJECT            = var.project_id
      MANAGED_AGENT_LOCATION          = var.managed_agent_location
      SKILLS_LOCATION                 = var.skills_location
      MANAGED_AGENT_ID                = var.managed_agent_id
      MANAGED_AGENT_NETWORK_ALLOWLIST = var.managed_agent_network_allowlist
      SKILLS_DIR                      = "skills"
    }
  }

  depends_on = [google_project_service.services]
}

output "managed_agent_id" {
  value       = var.managed_agent_id
  description = "ID of the managed skills agent."
}

output "skills_location" {
  value       = var.skills_location
  description = "Skill Registry location."
}
