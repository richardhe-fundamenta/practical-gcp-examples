-- All adk related logging entries from the past 24 hours
SELECT
  timestamp,
  severity,
  json_payload
FROM
  log_analytics._AllLogs
WHERE
  JSON_EXTRACT_SCALAR(json_payload, '$.labels.app') = 'adk'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY
  timestamp DESC,
  timestamp_unix_nanos DESC,
  insert_id DESC
LIMIT
  10000