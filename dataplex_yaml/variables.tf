variable "project_id" {
  type        = string
  description = "Google Cloud Project ID"
  default     = "rocketech-de-pgcp-sandbox"
}

variable "environment" {
  type        = string
  description = "Lifecycle environment"
  default     = "dev"
}

variable "source_project" {
  type        = string
  description = "Source project for the data"
  default     = "rocketech-de-pgcp-sandbox"
}

variable "export_project_id" {
  type        = string
  description = "Project ID to export the scan results"
  default = "rocketech-de-pgcp-sandbox"
}

variable "export_dataset_id" {
  type        = string
  description = "Dataset ID to export the scan results"
  default = "dataplex_dq_demo"
}

variable "export_table_id" {
  type        = string
  description = "Table ID to export the scan results"
  default = "dataplex_dq_demo_scan_results"
}

variable "data_quality_configs" {
  type = list(object({
    spec_file      = string
    source_dataset = string
    source_table   = string
  }))
  default = [
    {
      spec_file      = "rules/dataplex_dq_demo/customer_with_issues.yaml"
      source_dataset = "dataplex_dq_demo"
      source_table   = "customer_with_issues"
    },
    {
      spec_file      = "rules/dataplex_dq_demo/customer_perfect.yaml"
      source_dataset = "dataplex_dq_demo"
      source_table   = "customer_perfect"
    },
    # Add more configurations as needed
  ]
}