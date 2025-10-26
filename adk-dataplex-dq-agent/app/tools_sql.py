def dataplex_quality_analysis_query(dataplex_project_id, dataplex_dataset_id, dataplex_table_id, data_project_id, data_project_region, limit):

    return f"""
SELECT
  dq.data_source.table_project_id,
  dq.data_source.dataset_id,
  dq.data_source.table_id,
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', dq.job_end_time) AS job_end_time,
  dq.rule_name,
  dq.rule_dimension,
  dq.rule_passed,
  dq.rule_rows_evaluated,
  dq.rule_rows_passed,
  dq.rule_rows_passed_percent,
  labels.dq_level
FROM
  `{dataplex_project_id}`.`{dataplex_dataset_id}`.`{dataplex_table_id}` AS dq
INNER JOIN (
  SELECT
    data_source.table_project_id,
    data_source.dataset_id,
    data_source.table_id,
    job_end_time,
    created_on,
    ROW_NUMBER() OVER (PARTITION BY data_source.table_project_id, data_source.dataset_id, data_source.table_id ORDER BY job_end_time DESC, created_on DESC ) AS rn
  FROM
    `{dataplex_project_id}`.`{dataplex_dataset_id}`.`{dataplex_table_id}` ) AS latest_job
ON
  dq.data_source.table_project_id = latest_job.table_project_id
  AND dq.data_source.dataset_id = latest_job.dataset_id
  AND dq.data_source.table_id = latest_job.table_id
  AND dq.job_end_time = latest_job.job_end_time
  AND dq.created_on = latest_job.created_on
INNER JOIN (
  SELECT
    t1.table_catalog,
    t1.table_schema,
    t1.table_name,
    REGEXP_EXTRACT(t1.option_value, r'STRUCT\("dq_level"\s*,\s*"([^"]*)"\)') AS dq_level
  FROM
    `{data_project_id}`.`region-{data_project_region}`.INFORMATION_SCHEMA.TABLE_OPTIONS AS t1
  WHERE
    t1.option_name = 'labels'
    AND t1.option_value LIKE '%"dq_level"%' ) AS labels
ON
  dq.data_source.table_project_id = labels.table_catalog
  AND dq.data_source.dataset_id = labels.table_schema
  AND dq.data_source.table_id = labels.table_name
WHERE
  latest_job.rn = 1
  AND dq.rule_passed = FALSE
ORDER BY
  CASE labels.dq_level
    WHEN 'critical' THEN 1
    WHEN 'high' THEN 2
    WHEN 'medium' THEN 3
    WHEN 'low' THEN 4
    ELSE 5
END
  ,
  dq.job_end_time DESC,
  dq.data_source.table_project_id,
  dq.data_source.dataset_id,
  dq.data_source.table_id,
  dq.rule_name
LIMIT {limit};
"""

def dataplex_single_table_analysis_query(dataplex_project_id, dataplex_dataset_id, dataplex_table_id, table_to_analyse, limit):
    return f"""
SELECT
  t.data_source.table_project_id,
  t.data_source.dataset_id,
  t.data_source.table_id,
  t.data_quality_job_id,
  FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', t.job_end_time) AS job_end_time,
  t.job_quality_result.passed AS job_quality_result_passed,
  t.job_quality_result.score AS job_quality_result_score,
  t.job_quality_result.incremental_start AS job_quality_result_incremental_start,
  t.job_quality_result.incremental_end AS job_quality_result_incremental_end,
  t.rule_name,
  t.rule_description,
  t.rule_type,
  t.rule_column,
  t.rule_dimension,
  t.rule_threshold_percent,
  t.rule_passed,
  t.rule_rows_evaluated,
  t.rule_rows_passed,
  t.rule_rows_passed_percent
FROM
  `{dataplex_project_id}`.`{dataplex_dataset_id}`.`{dataplex_table_id}` AS t
INNER JOIN (
  SELECT
    data_source.table_project_id,
    data_source.dataset_id,
    data_source.table_id,
    job_end_time,
    created_on,
    ROW_NUMBER() OVER (PARTITION BY data_source.table_project_id, data_source.dataset_id, data_source.table_id ORDER BY job_end_time DESC, created_on DESC ) AS rn
  FROM
    `{dataplex_project_id}`.`{dataplex_dataset_id}`.`{dataplex_table_id}` ) AS latest_job
ON
  t.data_source.table_project_id = latest_job.table_project_id
  AND t.data_source.dataset_id = latest_job.dataset_id
  AND t.data_source.table_id = latest_job.table_id
  AND t.job_end_time = latest_job.job_end_time
  AND t.created_on = latest_job.created_on
WHERE
  latest_job.rn = 1
  AND t.rule_passed = FALSE
  AND CONCAT( t.data_source.table_project_id, '.', t.data_source.dataset_id, '.', t.data_source.table_id) LIKE '%{table_to_analyse}%'
ORDER BY
  t.job_end_time DESC
LIMIT {limit};
"""

def dataplex_debug_tool_query(dataplex_project_id, dataplex_dataset_id, dataplex_table_id, table_to_analyse, rule_name, limit):
    return f"""
SELECT
  t.data_source.table_project_id AS project_id,
  t.data_source.dataset_id AS dataset_id,
  t.data_source.table_id AS table_id,
  t.rule_name AS rule_name,
  t.rule_failed_records_query
FROM
  `{dataplex_project_id}`.`{dataplex_dataset_id}`.`{dataplex_table_id}` AS t
INNER JOIN (
  SELECT
    data_source.table_project_id,
    data_source.dataset_id,
    data_source.table_id,
    job_end_time,
    created_on,
    ROW_NUMBER() OVER (PARTITION BY data_source.table_project_id, data_source.dataset_id, data_source.table_id ORDER BY job_end_time DESC, created_on DESC ) AS rn
  FROM
    `{dataplex_project_id}`.`{dataplex_dataset_id}`.`{dataplex_table_id}` ) AS latest_job
ON
  t.data_source.table_project_id = latest_job.table_project_id
  AND t.data_source.dataset_id = latest_job.dataset_id
  AND t.data_source.table_id = latest_job.table_id
  AND t.job_end_time = latest_job.job_end_time
  AND t.created_on = latest_job.created_on
WHERE
  latest_job.rn = 1
  AND t.rule_passed = FALSE
  AND CONCAT( t.data_source.table_project_id, '.', t.data_source.dataset_id, '.', t.data_source.table_id) LIKE '%{table_to_analyse}%'
  AND t.rule_name LIKE '%{rule_name}%'
GROUP BY
ALL
LIMIT {limit};
"""