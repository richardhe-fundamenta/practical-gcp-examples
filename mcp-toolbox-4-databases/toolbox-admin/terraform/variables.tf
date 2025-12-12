variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run services and Artifact Registry"
  type        = string
  default     = "us-central1"
}

variable "artifact_registry_repository" {
  description = "Name of the Artifact Registry repository for Docker images"
  type        = string
  default     = "mcp-toolbox"
}

variable "admin_ui_service_name" {
  description = "Name of the Admin UI Cloud Run service"
  type        = string
  default     = "mcp-admin-ui"
}

variable "toolbox_service_name" {
  description = "Name of the MCP Toolbox Cloud Run service"
  type        = string
  default     = "mcp-toolbox"
}

variable "admin_ui_image" {
  description = "Docker image for Admin UI (e.g., us-central1-docker.pkg.dev/PROJECT_ID/mcp-toolbox/admin-ui:latest)"
  type        = string
}

variable "toolbox_image" {
  description = "Docker image for MCP Toolbox"
  type        = string
  default     = "us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:0.22.0"
}

variable "registry_dataset" {
  description = "BigQuery dataset name for query registry"
  type        = string
  default     = "example_mcp_toolbox_4_dbs"
}

variable "registry_table" {
  description = "BigQuery table name for query registry"
  type        = string
  default     = "query_registry"
}

variable "bigquery_source_name" {
  description = "BigQuery source name for the toolbox"
  type        = string
  default     = "bigquery-source"
}

variable "tools_file_path" {
  description = "Path to tools.yaml file in the container"
  type        = string
  default     = "/app/tools.yaml"
}

variable "admin_ui_service_account_name" {
  description = "Name for the Admin UI service account (will be created)"
  type        = string
  default     = "mcp-admin-ui-sa"
}

variable "toolbox_service_account_name" {
  description = "Name for the MCP Toolbox service account (will be created)"
  type        = string
  default     = "mcp-toolbox-sa"
}

variable "admin_ui_memory" {
  description = "Memory allocation for Admin UI service"
  type        = string
  default     = "512Mi"
}

variable "admin_ui_cpu" {
  description = "CPU allocation for Admin UI service"
  type        = string
  default     = "1"
}

variable "admin_ui_timeout" {
  description = "Request timeout for Admin UI service in seconds"
  type        = number
  default     = 300
}

variable "admin_ui_max_instances" {
  description = "Maximum number of instances for Admin UI"
  type        = number
  default     = 10
}

variable "toolbox_memory" {
  description = "Memory allocation for Toolbox service"
  type        = string
  default     = "1Gi"
}

variable "toolbox_cpu" {
  description = "CPU allocation for Toolbox service"
  type        = string
  default     = "2"
}

variable "toolbox_timeout" {
  description = "Request timeout for Toolbox service in seconds"
  type        = number
  default     = 300
}

variable "toolbox_max_instances" {
  description = "Maximum number of instances for Toolbox"
  type        = number
  default     = 10
}

variable "tools_yaml_secret_name" {
  description = "Name of the Secret Manager secret for tools.yaml"
  type        = string
  default     = "mcp-tools-yaml"
}

variable "tools_yaml_content" {
  description = "Content of the tools.yaml file to store in Secret Manager"
  type        = string
  sensitive   = true
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated access to Cloud Run services"
  type        = bool
  default     = true
}

variable "toolbox_address" {
  description = "Address for the toolbox server"
  type        = string
  default     = "0.0.0.0"
}

variable "toolbox_port" {
  description = "Port for the toolbox server"
  type        = number
  default     = 8080
}
