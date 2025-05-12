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

variable "data_quality_configs" {
  type = list(object({
    spec_file    = string
    source_dataset = string
    source_table = string
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