DECLARE
  QUERY_HASH STRING;
SET
  QUERY_HASH = "d1308ff1fd7b997651f451768a0183224e4ae96c13c264277c80059339b4dfc8";
WITH
  non_optimised AS (
  SELECT
    end_time,
    REGEXP_EXTRACT(query, r"AND refresh_date < '([0-9]{4}-[0-9]{2}-[0-9]{2})'") AS refresh_date,
    query_info.query_hashes.normalized_literals,
    query_info.optimization_details,
    TIMESTAMP_DIFF(end_time, start_time, MILLISECOND) AS elapsed_ms
  FROM
    region-US.INFORMATION_SCHEMA.JOBS_BY_PROJECT
  WHERE
    -- creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 HOUR)
    query_info.query_hashes.normalized_literals = QUERY_HASH
    AND query_info.optimization_details IS NULL
    ),
  optimised AS (
  SELECT
    end_time,
    REGEXP_EXTRACT(query, r"AND refresh_date < '([0-9]{4}-[0-9]{2}-[0-9]{2})'") AS refresh_date,
    query_info.query_hashes.normalized_literals,
    query_info.optimization_details,
    TIMESTAMP_DIFF(end_time, start_time, MILLISECOND) AS elapsed_ms
  FROM
    region-US.INFORMATION_SCHEMA.JOBS_BY_PROJECT
  WHERE
    -- creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 5 HOUR)
    query_info.query_hashes.normalized_literals = QUERY_HASH
    AND query_info.optimization_details IS NOT NULL )
SELECT
  refresh_date as all_until_date,
  SAFE_DIVIDE( non_optimised.elapsed_ms - optimised.elapsed_ms, non_optimised.elapsed_ms) * 100 AS percent_execution_time_saved,
  optimised.elapsed_ms AS new_elapsed_ms,
  non_optimised.elapsed_ms AS original_elapsed_ms,
FROM
  optimised
INNER JOIN
  non_optimised
USING
  (refresh_date)
ORDER BY
  refresh_date