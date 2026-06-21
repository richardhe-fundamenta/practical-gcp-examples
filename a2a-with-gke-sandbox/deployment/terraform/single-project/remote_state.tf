data "terraform_remote_state" "platform" {
  backend = "gcs"
  config = {
    bucket = "rocketech-de-pgcp-sandbox-tfstate"
    prefix = "gke-sandbox"
  }
}
