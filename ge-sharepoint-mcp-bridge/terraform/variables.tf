# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Richard He

variable "project_id" {
  description = "Project that hosts the MCP server and the Gemini Enterprise app. Always passed in, never committed."
  type        = string
}

variable "prefix" {
  description = "Prefix for every resource name. Change it to run several copies side by side in one project."
  type        = string
  default     = "spmcp"
}

variable "region" {
  description = "Region for Cloud Run, Artifact Registry, Cloud NAT and the audit log bucket."
  type        = string
  default     = "us-central1"
}

variable "gateway_region" {
  description = "Region for the egress Agent Gateway and its PSC network attachment. A Gemini Enterprise app in the 'global' location needs its gateway in us-central1, whatever region Cloud Run is in."
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "sharepoint-mcp-bridge"
}

variable "run_subnet_cidr" {
  description = "Subnet for Cloud Run Direct VPC egress."
  type        = string
  default     = "10.40.0.0/24"
}

variable "gateway_subnet_cidr" {
  description = "Subnet behind the Agent Gateway PSC network attachment."
  type        = string
  default     = "10.40.8.0/24"
}

variable "psc_endpoint_ip" {
  description = "Internal IP of the PSC endpoint for Google APIs. *.run.app resolves here inside the VPC. Must sit outside every subnet range."
  type        = string
  default     = "10.250.0.10"
}

variable "audit_retention_days" {
  description = "Retention of the audit log bucket."
  type        = number
  default     = 365
}

variable "extra_invokers" {
  description = "Extra members allowed to invoke Cloud Run, e.g. [\"user:you@example.com\"] for smoke tests from inside the VPC."
  type        = list(string)
  default     = []
}

variable "allow_anonymous_links" {
  description = "Let create_sharing_link create anonymous ('anyone with the link') links. Microsoft 365 tenant policy still applies."
  type        = bool
  default     = false
}
