variable "infra_project" {
  type        = string
  description = "GCP project that hosts the bucket, Artifact Registry repo, and Cloud Run Job."
  default     = "rocketech-de-pgcp-sandbox"
}

variable "region" {
  type        = string
  description = "Region for the bucket, Artifact Registry, and Cloud Run Job."
  default     = "us-central1"
}

variable "bucket_name" {
  type        = string
  description = "GCS bucket for render payloads, temp cache, and outputs."
  default     = "script-to-video-rocketech-de-pgcp-sandbox"
}

variable "job_name" {
  type        = string
  description = "Cloud Run Job name."
  default     = "script-to-video-render"
}

variable "repo_name" {
  type        = string
  description = "Artifact Registry repository name."
  default     = "script-to-video"
}

variable "sa_name" {
  type        = string
  description = "Account ID of the dedicated render service account."
  default     = "script-to-video-render"
}

variable "render_project" {
  type        = string
  description = "Project where the render's Vertex AI / TTS calls run (the GUI sidebar project_id). Defaults to infra_project."
  default     = ""
}

variable "web_sa_name" {
  type        = string
  description = "Account ID of the web (Streamlit) service's dedicated service account."
  default     = "script-to-video-web"
}

variable "service_name" {
  type        = string
  description = "Cloud Run service name for the web app."
  default     = "script-to-video-web"
}

variable "iap_domain" {
  description = "Google Workspace domain allowed through IAP (everyone in it can sign in)."
  type        = string
  default     = "rocketech.co.uk"
}
