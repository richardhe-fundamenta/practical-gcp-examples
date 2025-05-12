# Copyright 2023 Google LLC
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

variable "project_id" {
  type        = string
  description = "Google Cloud Project ID"
}

variable "region" {
  type        = string
  description = "Google Cloud Region"
  default     = "europe-west2"
}

variable "labels" {
  type = map(string)
  description = "A map of labels to apply to contained resources."
  default = { "auto-data-quality" = true }
}

variable "enable_apis" {
  type        = string
  description = "Whether or not to enable underlying apis in this solution. ."
  default     = true
}

variable "environment" {
  type        = string
  description = "Lifecycle environment"
  default     = "dev"
}

variable "source_project" {
  type        = string
  description = "Source project for the data"
}


variable "source_dataset" {
  type        = string
  description = "Source dataset for the data"
}

variable "source_table" {
  type        = string
  description = "Source table for the data"
}

variable "data_quality_spec_file" {
  type        = string
  description = "Path to a YAML file containing DataQualityScan related setting. Input content can use either camelCase or snake_case. Variables description are provided in https://cloud.google.com/dataplex/docs/reference/rest/v1/DataQualitySpec."
}