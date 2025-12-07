-- BigQuery schema for the query registry table
-- This table stores all query definitions for the MCP Toolbox
-- Note: ${REGISTRY_DATASET} and ${REGISTRY_TABLE} will be substituted by deployment scripts

-- Create the dataset if it doesn't exist
CREATE SCHEMA IF NOT EXISTS ${REGISTRY_DATASET}
OPTIONS (
  description = "Configuration storage for MCP Toolbox",
  location = "us-central1"
);

-- Create the query registry table
CREATE TABLE IF NOT EXISTS ${REGISTRY_DATASET}.${REGISTRY_TABLE} (
  -- Unique identifier for the query
  query_name STRING NOT NULL OPTIONS (description = "Unique name for the query tool"),

  -- Category for organization into toolsets
  query_category STRING NOT NULL OPTIONS (description = "Category for toolset organization (e.g., analytics, operations, reporting)"),

  -- The actual BigQuery SQL statement
  query_sql STRING NOT NULL OPTIONS (description = "The BigQuery SQL statement to execute"),

  -- Human-readable description
  description STRING OPTIONS (description = "Description of what the query does"),

  -- Parameters as JSON array
  parameters JSON OPTIONS (description = "JSON array of parameter definitions"),

  -- Enable/disable flag
  enabled BOOL NOT NULL OPTIONS (description = "Whether this query is active"),

  -- Audit timestamps
  created_at TIMESTAMP NOT NULL OPTIONS (description = "When the query was created"),
  updated_at TIMESTAMP NOT NULL OPTIONS (description = "When the query was last updated"),

  -- Optional metadata
  created_by STRING OPTIONS (description = "User who created the query"),
  tags ARRAY<STRING> OPTIONS (description = "Tags for additional categorization"),
  estimated_cost_tier STRING OPTIONS (description = "LOW, MEDIUM, HIGH - estimated query cost"),
  max_execution_time_seconds INT64 OPTIONS (description = "Maximum expected execution time")
)
OPTIONS (
  description = "Registry of all BigQuery queries for MCP Toolbox",
  labels = [("component", "mcp-toolbox"), ("type", "registry")]
);

-- Create a unique index on query_name
-- Note: BigQuery doesn't support UNIQUE constraints, so we rely on application logic
-- to enforce uniqueness. Consider using MERGE or INSERT ... SELECT to check for duplicates.

-- Create a view for active queries only (for convenience)
CREATE OR REPLACE VIEW ${REGISTRY_DATASET}.active_queries AS
SELECT
  query_name,
  query_category,
  query_sql,
  description,
  parameters,
  created_at,
  updated_at,
  created_by,
  tags,
  estimated_cost_tier,
  max_execution_time_seconds
FROM ${REGISTRY_DATASET}.${REGISTRY_TABLE}
WHERE enabled = true;

-- Example: Insert a sample query
-- This is commented out by default
/*
INSERT INTO ${REGISTRY_DATASET}.${REGISTRY_TABLE} (
  query_name,
  query_category,
  query_sql,
  description,
  parameters,
  enabled,
  created_by,
  tags,
  estimated_cost_tier
) VALUES (
  'get_user_by_id',
  'analytics',
  'SELECT user_id, username, email, created_at FROM `project.dataset.users` WHERE user_id = @user_id',
  'Retrieve user information by user ID',
  JSON '[{"name": "user_id", "type": "string", "description": "The user ID to look up", "required": true}]',
  true,
  'admin@example.com',
  ['users', 'lookup'],
  'LOW'
);
*/
