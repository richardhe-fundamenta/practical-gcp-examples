WITH daily_failures AS (
    SELECT
        data_source.table_id,
        rule_name,
        DATE(job_start_time) AS failure_date,
        rule_failed_records_query,
        ROW_NUMBER() OVER(PARTITION BY data_source.table_id, rule_name, DATE(job_start_time) ORDER BY job_start_time DESC) AS rn
    FROM
        `rocketech-de-pgcp-sandbox.dataplex_dq_demo.dataplex_dq_demo_scan_results` AS t1
    WHERE
        t1.rule_rows_passed_percent < 100
),
daily_failures_with_latest_query AS (
    SELECT
        table_id,
        rule_name,
        failure_date,
        rule_failed_records_query
    FROM
        daily_failures
    WHERE
        rn = 1
)
SELECT
    dfwq.table_id,
    dfwq.rule_name,
    dfwq.failure_date,
    dfwq.rule_failed_records_query,
    COUNT(df.rule_name) AS daily_failure_count,
    AI.GENERATE(
                prompt => 'Summarize this SQL query in under 20 words: ' || dfwq.rule_failed_records_query,
                connection_id => 'europe-west2.vertex_ai_remote_models',
                endpoint => 'gemini-1.5-flash-002' -- Gemini 2.0 flash isn't yet available in the London region
            ) AS failure_description
FROM
    daily_failures_with_latest_query dfwq
JOIN
    daily_failures df ON
        dfwq.table_id = df.table_id AND
        dfwq.rule_name = df.rule_name AND
        dfwq.failure_date = df.failure_date
GROUP BY
    dfwq.table_id,
    dfwq.rule_name,
    dfwq.failure_date,
    dfwq.rule_failed_records_query
ORDER BY
    dfwq.failure_date desc,
    daily_failure_count desc,
    dfwq.table_id asc,
    dfwq.rule_name asc
