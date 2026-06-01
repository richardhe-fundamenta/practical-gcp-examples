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

# Durable host Agent Engine (reasoningEngine) under which the harness lazily creates a
# per-session code-exec sandbox (see app/sandbox/client.py: get_or_create_sandbox). A bare
# "stub" engine with no deployed agent code is sufficient — it only serves as the parent
# resource for sandboxes. It must be PERSISTENT (not the throwaway engine used during
# earlier deploy debugging) so the per-session lifecycle has a stable host to create under.
resource "google_vertex_ai_reasoning_engine" "sandbox_host" {
  display_name = "${var.project_name}-sandbox-host"
  description  = "Durable host engine for per-session code-exec sandboxes (analyst-harness)."

  # us-central1 is REQUIRED: the Agent Engine code-exec sandbox API is us-central1-only,
  # independent of where the Cloud Run service runs (app.config pins sandbox_region too).
  region  = "us-central1"
  project = var.project_id

  depends_on = [resource.google_project_service.services]
}

output "agent_engine_name" {
  description = "Full resource name of the durable host Agent Engine used for AGENT_ENGINE_NAME."
  # .id is the full path projects/.../reasoningEngines/<id>; .name is only the bare id,
  # which the sandbox API does not accept.
  value = google_vertex_ai_reasoning_engine.sandbox_host.id
}
