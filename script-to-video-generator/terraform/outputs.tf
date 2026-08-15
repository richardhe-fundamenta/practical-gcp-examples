output "bucket" {
  value       = google_storage_bucket.render.name
  description = "Render bucket name."
}

output "job_name" {
  value       = google_cloud_run_v2_job.render.name
  description = "Cloud Run Job name."
}

output "service_account" {
  value       = google_service_account.render.email
  description = "Dedicated render Job service account."
}

output "image" {
  value       = local.image
  description = "Container image the Job runs."
}

output "service_url" {
  value       = google_cloud_run_v2_service.web.uri
  description = "URL of the web app (behind IAP; sign in with a Workspace account in iap_domain)."
}
