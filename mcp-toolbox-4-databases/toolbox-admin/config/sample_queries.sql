-- Sample queries using BigQuery Public Datasets
-- These queries use real, publicly accessible datasets
-- Note: ${REGISTRY_DATASET}.${REGISTRY_TABLE} will be substituted by deployment scripts

-- Analytics queries using USA Names public dataset
INSERT INTO ${REGISTRY_DATASET}.${REGISTRY_TABLE} (
  query_name,
  query_category,
  query_sql,
  description,
  parameters,
  enabled,
  created_at,
  updated_at,
  created_by,
  tags,
  estimated_cost_tier
) VALUES
(
  'get_popular_names_by_year',
  'analytics',
  'SELECT name, gender, SUM(number) as total_count FROM `bigquery-public-data.usa_names.usa_1910_current` WHERE year = @year GROUP BY name, gender ORDER BY total_count DESC LIMIT 10',
  'Get top 10 most popular baby names for a specific year',
  JSON '[{"name": "year", "type": "integer", "description": "The year to query (1910-current)", "required": true}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'analytics-team@example.com',
  ['names', 'demographics', 'trends'],
  'LOW'
),
(
  'get_name_trend_over_time',
  'analytics',
  'SELECT year, name, gender, SUM(number) as count FROM `bigquery-public-data.usa_names.usa_1910_current` WHERE name = @name AND gender = @gender GROUP BY year, name, gender ORDER BY year',
  'Track popularity trend of a specific name over time',
  JSON '[{"name": "name", "type": "string", "description": "The name to track", "required": true}, {"name": "gender", "type": "string", "description": "Gender: M or F", "required": true}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'analytics-team@example.com',
  ['names', 'trends', 'historical'],
  'LOW'
),
(
  'get_name_diversity_by_decade',
  'analytics',
  'SELECT CAST(FLOOR(year/10)*10 AS INT64) as decade, COUNT(DISTINCT name) as unique_names, SUM(number) as total_births FROM `bigquery-public-data.usa_names.usa_1910_current` WHERE year >= @start_year AND year <= @end_year GROUP BY decade ORDER BY decade',
  'Analyze name diversity by decade',
  JSON '[{"name": "start_year", "type": "integer", "description": "Start year", "required": true}, {"name": "end_year", "type": "integer", "description": "End year", "required": true}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'analytics-team@example.com',
  ['diversity', 'demographics', 'trends'],
  'MEDIUM'
);

-- Operations queries using Stack Overflow public dataset
INSERT INTO ${REGISTRY_DATASET}.${REGISTRY_TABLE} (
  query_name,
  query_category,
  query_sql,
  description,
  parameters,
  enabled,
  created_at,
  updated_at,
  created_by,
  tags,
  estimated_cost_tier
) VALUES
(
  'get_popular_stackoverflow_tags',
  'operations',
  'SELECT tag_name, COUNT(*) as tag_count FROM `bigquery-public-data.stackoverflow.tags`, UNNEST(SPLIT(tags, "|")) as tag_name WHERE creation_date >= TIMESTAMP(@start_date) AND creation_date <= TIMESTAMP(@end_date) GROUP BY tag_name ORDER BY tag_count DESC LIMIT @top_n',
  'Get most popular Stack Overflow tags for a date range',
  JSON '[{"name": "start_date", "type": "string", "description": "Start date (YYYY-MM-DD)", "required": true}, {"name": "end_date", "type": "string", "description": "End date (YYYY-MM-DD)", "required": true}, {"name": "top_n", "type": "integer", "description": "Number of top tags to return", "required": true, "default": 20}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'ops-team@example.com',
  ['stackoverflow', 'tags', 'trends'],
  'MEDIUM'
),
(
  'get_stackoverflow_posts_by_tag',
  'operations',
  'SELECT id, title, view_count, answer_count, score, creation_date FROM `bigquery-public-data.stackoverflow.posts_questions` WHERE tags LIKE CONCAT("%", @tag, "%") ORDER BY creation_date DESC LIMIT @limit',
  'Get recent Stack Overflow questions by tag',
  JSON '[{"name": "tag", "type": "string", "description": "Tag to search for (e.g., python, javascript)", "required": true}, {"name": "limit", "type": "integer", "description": "Maximum number of results", "required": true, "default": 100}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'ops-team@example.com',
  ['stackoverflow', 'questions', 'search'],
  'MEDIUM'
),
(
  'get_stackoverflow_user_activity',
  'operations',
  'SELECT owner_user_id, COUNT(*) as post_count, AVG(score) as avg_score, SUM(view_count) as total_views FROM `bigquery-public-data.stackoverflow.posts_questions` WHERE owner_user_id = @user_id GROUP BY owner_user_id',
  'Get Stack Overflow user activity statistics',
  JSON '[{"name": "user_id", "type": "integer", "description": "Stack Overflow user ID", "required": true}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'ops-team@example.com',
  ['stackoverflow', 'users', 'analytics'],
  'LOW'
);

-- Reporting queries using Chicago Crime public dataset
INSERT INTO ${REGISTRY_DATASET}.${REGISTRY_TABLE} (
  query_name,
  query_category,
  query_sql,
  description,
  parameters,
  enabled,
  created_at,
  updated_at,
  created_by,
  tags,
  estimated_cost_tier
) VALUES
(
  'get_chicago_crime_by_type',
  'reporting',
  'SELECT primary_type, COUNT(*) as incident_count FROM `bigquery-public-data.chicago_crime.crime` WHERE DATE(date) BETWEEN DATE(@start_date) AND DATE(@end_date) GROUP BY primary_type ORDER BY incident_count DESC',
  'Get Chicago crime incidents by type for a date range',
  JSON '[{"name": "start_date", "type": "string", "description": "Start date (format YYYY-MM-DD)", "required": true}, {"name": "end_date", "type": "string", "description": "End date (format YYYY-MM-DD)", "required": true}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'reporting-team@example.com',
  ['crime', 'chicago', 'statistics'],
  'MEDIUM'
),
(
  'get_chicago_crime_by_location',
  'reporting',
  'SELECT location_description, COUNT(*) as incident_count, ARRAY_AGG(DISTINCT primary_type LIMIT 5) as top_crime_types FROM `bigquery-public-data.chicago_crime.crime` WHERE DATE(date) = DATE(@report_date) GROUP BY location_description ORDER BY incident_count DESC LIMIT 20',
  'Get Chicago crime incidents by location for a specific date',
  JSON '[{"name": "report_date", "type": "string", "description": "Date to report on (format YYYY-MM-DD)", "required": true}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'reporting-team@example.com',
  ['crime', 'chicago', 'location'],
  'MEDIUM'
),
(
  'get_chicago_crime_trends',
  'reporting',
  'SELECT EXTRACT(YEAR FROM date) as year, EXTRACT(MONTH FROM date) as month, COUNT(*) as incident_count, COUNT(DISTINCT primary_type) as crime_types FROM `bigquery-public-data.chicago_crime.crime` WHERE DATE(date) >= DATE(@start_date) GROUP BY year, month ORDER BY year, month',
  'Get Chicago crime trends by month',
  JSON '[{"name": "start_date", "type": "string", "description": "Start date for trend analysis (format YYYY-MM-DD)", "required": true}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'reporting-team@example.com',
  ['crime', 'trends', 'monthly'],
  'HIGH'
);

-- ML/Data Science queries using public datasets
INSERT INTO ${REGISTRY_DATASET}.${REGISTRY_TABLE} (
  query_name,
  query_category,
  query_sql,
  description,
  parameters,
  enabled,
  created_at,
  updated_at,
  created_by,
  tags,
  estimated_cost_tier
) VALUES
(
  'get_name_features_for_ml',
  'ml',
  'SELECT name, gender, AVG(number) as avg_count, STDDEV(number) as stddev_count, COUNT(*) as year_count, MIN(year) as first_year, MAX(year) as last_year FROM `bigquery-public-data.usa_names.usa_1910_current` WHERE year >= @min_year GROUP BY name, gender HAVING year_count >= @min_year_count',
  'Extract name features for ML model training',
  JSON '[{"name": "min_year", "type": "integer", "description": "Minimum year to include", "required": true}, {"name": "min_year_count", "type": "integer", "description": "Minimum number of years name must appear", "required": true, "default": 10}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'ml-team@example.com',
  ['ml', 'features', 'names'],
  'HIGH'
),
(
  'get_crime_prediction_features',
  'ml',
  'SELECT primary_type, location_description, EXTRACT(HOUR FROM date) as hour, EXTRACT(DAYOFWEEK FROM date) as day_of_week, COUNT(*) as historical_count FROM `bigquery-public-data.chicago_crime.crime` WHERE DATE(date) >= DATE(@training_start_date) AND DATE(date) <= DATE(@training_end_date) GROUP BY primary_type, location_description, hour, day_of_week',
  'Extract crime features for predictive modeling',
  JSON '[{"name": "training_start_date", "type": "string", "description": "Training data start date (format YYYY-MM-DD)", "required": true}, {"name": "training_end_date", "type": "string", "description": "Training data end date (format YYYY-MM-DD)", "required": true}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'ml-team@example.com',
  ['ml', 'crime', 'prediction'],
  'HIGH'
);

-- Admin queries using INFORMATION_SCHEMA
INSERT INTO ${REGISTRY_DATASET}.${REGISTRY_TABLE} (
  query_name,
  query_category,
  query_sql,
  description,
  parameters,
  enabled,
  created_at,
  updated_at,
  created_by,
  tags,
  estimated_cost_tier
) VALUES
(
  'get_dataset_table_info',
  'admin',
  'SELECT table_name, table_type, TIMESTAMP_MILLIS(creation_time) as created, ROUND(size_bytes/1024/1024/1024, 2) as size_gb, row_count FROM `bigquery-public-data.usa_names.__TABLES__` ORDER BY size_bytes DESC',
  'Get table information for usa_names public dataset',
  JSON '[]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'admin-team@example.com',
  ['metadata', 'admin', 'tables'],
  'LOW'
),
(
  'get_query_execution_stats',
  'admin',
  'SELECT user_email, COUNT(*) as query_count, SUM(total_bytes_processed) / POW(10, 12) as total_tb_processed, AVG(total_slot_ms) as avg_slot_ms FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours_ago HOUR) AND job_type = "QUERY" AND state = "DONE" GROUP BY user_email ORDER BY total_tb_processed DESC',
  'Get query execution statistics for the last N hours',
  JSON '[{"name": "hours_ago", "type": "integer", "description": "Number of hours to look back", "required": true, "default": 24}]',
  true,
  CURRENT_TIMESTAMP(),
  CURRENT_TIMESTAMP(),
  'admin-team@example.com',
  ['performance', 'monitoring', 'queries'],
  'LOW'
);
