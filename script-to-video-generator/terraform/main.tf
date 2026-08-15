locals {
  render_project = coalesce(var.render_project, var.infra_project)
  image          = "${var.region}-docker.pkg.dev/${var.infra_project}/${var.repo_name}/render:latest"
  web_image      = "${var.region}-docker.pkg.dev/${var.infra_project}/${var.repo_name}/web:latest"

  # Rebuild an image only when its build context actually changes.
  build_files = fileset("${path.module}/..", "deck/**")

  # Heavy base (torch/whisper, Chromium, app deps). Rebuilds only when deps or
  # the base recipe change — never on code edits. Pinned into the app build by
  # its hash-derived tag so the thin build can't grab a half-pushed base.
  base_build_hash = sha256(join(",", [
    filesha256("${path.module}/../Dockerfile.base"),
    filesha256("${path.module}/../cloudbuild.base.yaml"),
    filesha256("${path.module}/../pyproject.toml"),
    filesha256("${path.module}/../uv.lock"),
  ]))
  base_image = "${var.region}-docker.pkg.dev/${var.infra_project}/${var.repo_name}/render-base:${substr(local.base_build_hash, 0, 16)}"

  # Thin app image: FROM base + COPY deck. Rebuilds on code changes (fast) or
  # when the base changes (base_build_hash pulls the new base into scope).
  build_hash = sha256(join(",", concat(
    [local.base_build_hash],
    [filesha256("${path.module}/../build/Dockerfile")],
    [filesha256("${path.module}/../build/cloudbuild.render.yaml")],
    [for f in local.build_files : filesha256("${path.module}/../${f}")],
  )))
  web_build_hash = sha256(join(",", concat(
    [filesha256("${path.module}/../build/Dockerfile.service")],
    [filesha256("${path.module}/../build/cloudbuild.web.yaml")],
    [filesha256("${path.module}/../app.py")],
    [filesha256("${path.module}/../pyproject.toml")],
    [filesha256("${path.module}/../uv.lock")],
    [for f in local.build_files : filesha256("${path.module}/../${f}")],
  )))
}

resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "secretmanager.googleapis.com",
    "iap.googleapis.com",
  ])
  project            = var.infra_project
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "render" {
  name                        = var.bucket_name
  project                     = var.infra_project
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
  depends_on                  = [google_project_service.services]
}

resource "google_artifact_registry_repository" "repo" {
  repository_id = var.repo_name
  project       = var.infra_project
  location      = var.region
  format        = "DOCKER"
  depends_on    = [google_project_service.services]
}

# Dedicated least-privilege runtime identity for the render Job (not the default Compute SA).
resource "google_service_account" "render" {
  account_id   = var.sa_name
  project      = var.infra_project
  display_name = "script-to-video render Job"
  depends_on   = [google_project_service.services]
}

# Job SA: read/write the render bucket only.
resource "google_storage_bucket_iam_member" "render_sa_bucket" {
  bucket = google_storage_bucket.render.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.render.email}"
}

# Job SA: call Vertex AI (Gemini/Imagen/Veo) in the render target project.
resource "google_project_iam_member" "render_sa_aiplatform" {
  project = local.render_project
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.render.email}"
}

# Job SA: consume enabled APIs (covers Cloud Text-to-Speech, which has no dedicated role).
resource "google_project_iam_member" "render_sa_serviceusage" {
  project = local.render_project
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.render.email}"
}

# Build + push the heavy base image. Slow (~10m: torch/whisper + Chromium) but
# rebuilds only when deps or the base recipe change. E2_HIGHCPU_8 is set in the
# cloudbuild config. Custom machine types are billed (no free tier) — the
# intended tradeoff for speed on the rare rebuild.
resource "terraform_data" "render_base_build" {
  triggers_replace = local.base_build_hash

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = "gcloud builds submit ${path.module}/.. --config=${path.module}/../cloudbuild.base.yaml --substitutions=_IMAGE=${local.base_image} --project ${var.infra_project}"
  }

  depends_on = [
    google_artifact_registry_repository.repo,
    google_project_service.services,
  ]
}

# Build + push the thin app image FROM the prebuilt base — ~1-2m vs ~10m, so
# this is what most (code-only) changes trigger.
resource "terraform_data" "image_build" {
  triggers_replace = local.build_hash

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = "gcloud builds submit ${path.module}/.. --config=${path.module}/../build/cloudbuild.render.yaml --substitutions=_IMAGE=${local.image},_BASE=${local.base_image} --project ${var.infra_project}"
  }

  depends_on = [terraform_data.render_base_build]
}

resource "google_cloud_run_v2_job" "render" {
  name                = var.job_name
  project             = var.infra_project
  location            = var.region
  deletion_protection = false

  template {
    # Bust the pinned :latest -> digest on every image rebuild; without this a
    # new :latest push doesn't reach executions (Terraform sees no diff).
    labels = { build-hash = substr(local.build_hash, 0, 16) }

    template {
      service_account = google_service_account.render.email
      max_retries     = 1
      timeout         = "3600s"

      containers {
        image = local.image
        resources {
          # Bumped from 2/4Gi: the render/record step now runs Chromium inside a
          # Cloud Run sandbox that shares this instance's CPU/mem, and both the
          # bind-mounted work dir and the sandbox --write overlay are tmpfs (count
          # against memory on Cloud Run). Tunable down if renders stay small.
          limits = {
            cpu    = "4"
            memory = "8Gi"
          }
        }
        env {
          name  = "GCS_BUCKET"
          value = var.bucket_name
        }
        # Isolate the model-authored-JS render step in a no-egress sandbox
        # (deck.render.record._run_browser). Requires the sandbox launcher, enabled on
        # the Job by terraform_data.render_sandbox_launcher below.
        env {
          name  = "DECK_RENDER_SANDBOX"
          value = "1"
        }
        # ElevenLabs API key for the optional cloned-voice TTS path. The secret
        # is created out of band (gcloud); Cloud Run injects its value as the env
        # var record.py reads. Renders using Gemini TTS simply ignore it.
        env {
          name = "ELEVENLABS_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.elevenlabs.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [terraform_data.image_build]
}

# Enable the Cloud Run sandbox launcher on the render Job (public preview / BETA
# track). The google_cloud_run_v2_job resource doesn't model `sandboxLauncher`,
# so assert it out-of-band with gcloud.
#
# Re-asserted on EVERY apply, not just image rebuilds. Any in-place update
# Terraform makes to the Job rewrites the container spec WITHOUT the unmodeled
# field, so an apply that touches the Job for any other reason silently strips
# the launcher — and the next render dies on a missing
# /usr/local/gcp/bin/sandbox, after paying for compose and TTS.
#
# plantimestamp() (not the Job's etag: that changes mid-apply, which trips
# "Provider produced inconsistent final plan") makes this resource replace on
# every plan. Intentional: the gcloud call is idempotent and takes ~4s, and one
# permanently dirty plan line is cheaper than a silently unsandboxed render.
# Delete this whole resource once the Cloud Run v2 provider models
# sandboxLauncher natively.
resource "terraform_data" "render_sandbox_launcher" {
  triggers_replace = [local.build_hash, plantimestamp()]

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = "gcloud beta run jobs update ${var.job_name} --sandbox-launcher --project ${var.infra_project} --region ${var.region}"
  }

  depends_on = [google_cloud_run_v2_job.render]
}

# ElevenLabs key for the optional cloned-voice TTS path. Created empty so a fresh
# project stands up without it; put the real key in with
#   echo -n "<key>" | gcloud secrets versions add elevenlabs-api-key --data-file=- --project <project>
# Later applies ignore the value, so Terraform never clobbers the real key.
resource "google_secret_manager_secret" "elevenlabs" {
  secret_id = "elevenlabs-api-key"
  project   = var.infra_project
  replication {
    auto {}
  }
  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "elevenlabs_placeholder" {
  secret      = google_secret_manager_secret.elevenlabs.id
  secret_data = "placeholder-replace-me"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_iam_member" "render_elevenlabs" {
  secret_id = google_secret_manager_secret.elevenlabs.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.render.email}"
}

# --- web app: Cloud Run service behind IAP -----------------------------------

# Dedicated runtime identity for the web service.
resource "google_service_account" "web" {
  account_id   = var.web_sa_name
  project      = var.infra_project
  display_name = "script-to-video web service"
  depends_on   = [google_project_service.services]
}

resource "google_storage_bucket_iam_member" "web_bucket" {
  bucket = google_storage_bucket.render.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.web.email}"
}

# The web service runs deck generation in-process (synchronous), which calls
# Vertex AI (Gemini) — so its SA needs aiplatform.user, mirroring the render SA.
resource "google_project_iam_member" "web_sa_aiplatform" {
  project = var.infra_project
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.web.email}"
}

# Minimal role to execute the render Job with container overrides (DECK_NAME).
resource "google_project_iam_custom_role" "job_runner" {
  role_id     = "deckJobRunner"
  project     = var.infra_project
  title       = "Deck Job Runner"
  description = "Execute the render Cloud Run Job with container overrides."
  permissions = [
    "run.jobs.run",
    "run.jobs.runWithOverrides",
    "run.jobs.get",
  ]
}

resource "google_cloud_run_v2_job_iam_member" "web_job_runner" {
  name     = google_cloud_run_v2_job.render.name
  location = var.region
  project  = var.infra_project
  role     = google_project_iam_custom_role.job_runner.id
  member   = "serviceAccount:${google_service_account.web.email}"
}

# Build + push the slim web image, re-running only on source changes.
resource "terraform_data" "web_image_build" {
  triggers_replace = local.web_build_hash

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = "gcloud builds submit ${path.module}/.. --config=${path.module}/../build/cloudbuild.web.yaml --substitutions=_IMAGE=${local.web_image} --project ${var.infra_project}"
  }

  depends_on = [
    google_artifact_registry_repository.repo,
    google_project_service.services,
  ]
}

resource "google_cloud_run_v2_service" "web" {
  # google-beta: iap_enabled is beta-only in provider 6.x.
  provider            = google-beta
  name                = var.service_name
  project             = var.infra_project
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  # Identity-Aware Proxy fronts the service: every request must carry a Google
  # login, and only members granted iap.httpsResourceAccessor below get through
  # (see google_iap_web_cloud_run_service_iam_member). The app itself has no
  # login code — IAP is the gate, and it runs before any container request.
  iap_enabled = true

  template {
    # Same :latest-digest cache-bust as the render Job (see its labels comment).
    labels           = { build-hash = substr(local.web_build_hash, 0, 16) }
    service_account  = google_service_account.web.email
    session_affinity = true # keep the Streamlit WebSocket on one instance

    scaling {
      min_instance_count = 0 # scale to zero
      max_instance_count = 1 # single instance; Streamlit session state is in-memory
    }

    containers {
      image = local.web_image
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
      ports {
        container_port = 8080
      }
      env {
        name  = "GCS_BUCKET"
        value = var.bucket_name
      }
      env {
        name  = "INFRA_PROJECT"
        value = var.infra_project
      }
      env {
        name  = "REGION"
        value = var.region
      }
      env {
        name  = "DECK_JOB_NAME"
        value = var.job_name
      }
    }
  }

  depends_on = [terraform_data.web_image_build]
}

# IAP needs its own service agent, and that agent needs run.invoker to forward
# an authenticated request to the service. Without this the service returns 403
# to everyone, IAP included.
resource "google_project_service_identity" "iap" {
  provider = google-beta
  project  = var.infra_project
  service  = "iap.googleapis.com"

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  name     = google_cloud_run_v2_service.web.name
  project  = var.infra_project
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_project_service_identity.iap.email}"
}

# Who may pass through IAP. `domain:` covers every Google Workspace account in
# the domain, so access follows the directory — no per-user Terraform edits, and
# offboarding a person in Workspace revokes their access here too.
resource "google_iap_web_cloud_run_service_iam_member" "domain_access" {
  project                = var.infra_project
  location               = var.region
  cloud_run_service_name = google_cloud_run_v2_service.web.name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = "domain:${var.iap_domain}"
}
