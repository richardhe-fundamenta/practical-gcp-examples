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

resource "google_dataplex_datascan" "dq_scan" {
  location = var.region
  project  = var.project_id
  data_scan_id = replace("${local.env}--${var.source_dataset}--${var.source_table}", "_", "-")
  labels = {
    the_environment = local.env
  }

  data {
    resource = "//bigquery.googleapis.com/projects/${var.source_project}/datasets/${var.source_dataset}/tables/${var.source_table}"
  }

  execution_spec {
    trigger {
      on_demand {}
    }
  }

  # Custom logic to parse out rules metadata from a local rules.yaml file
  data_quality_spec {
    sampling_percent = try(local.sampling_percent, null)
    row_filter = try(local.row_filter, null)

    dynamic "rules" {
      for_each = local.rules
      content {
        column = try(rules.value.column, null)
        ignore_null = try(rules.value.ignore_null, null)
        dimension = rules.value.dimension
        description = try(rules.value.description, null)
        name = try(rules.value.name, null)
        threshold = try(rules.value.threshold, null)

        dynamic "non_null_expectation" {
          for_each = try(rules.value.non_null_expectation, null) != null ? [""] : []
          content {
          }
        }

        dynamic "range_expectation" {
          for_each = try(rules.value.range_expectation, null) != null ? [""] : []
          content {
            min_value = try(rules.value.range_expectation.min_value, null)
            max_value = try(rules.value.range_expectation.max_value, null)
            strict_min_enabled = try(rules.value.range_expectation.strict_min_enabled, null)
            strict_max_enabled = try(rules.value.range_expectation.strict_max_enabled, null)
          }
        }

        dynamic "set_expectation" {
          for_each = try(rules.value.set_expectation, null) != null ? [""] : []
          content {
            values = rules.value.set_expectation.values
          }
        }

        dynamic "sql_assertion" {
          for_each = try(rules.value.sql_assertion, null) != null ? [""] : []
          content {
            sql_statement = rules.value.sql_assertion.sql_statement
          }
        }

        dynamic "uniqueness_expectation" {
          for_each = try(rules.value.uniqueness_expectation, null) != null ? [""] : []
          content {
          }
        }

        dynamic "regex_expectation" {
          for_each = try(rules.value.regex_expectation, null) != null ? [""] : []
          content {
            regex = rules.value.regex_expectation.regex
          }
        }

        dynamic "statistic_range_expectation" {
          for_each = try(rules.value.statistic_range_expectation, null) != null ? [""] : []
          content {
            min_value = try(rules.value.statistic_range_expectation.min_value, null)
            max_value = try(rules.value.statistic_range_expectation.max_value, null)
            strict_min_enabled = try(rules.value.statistic_range_expectation.strict_min_enabled, null)
            strict_max_enabled = try(rules.value.statistic_range_expectation.strict_max_enabled, null)
            statistic = rules.value.statistic_range_expectation.statistic
          }
        }

        dynamic "row_condition_expectation" {
          for_each = try(rules.value.row_condition_expectation, null) != null ? [""] : []
          content {
            sql_expression = rules.value.row_condition_expectation.sql_expression
          }
        }

        dynamic "table_condition_expectation" {
          for_each = try(rules.value.table_condition_expectation, null) != null ? [""] : []
          content {
            sql_expression = rules.value.table_condition_expectation.sql_expression
          }
        }

      }
    }
  }

}