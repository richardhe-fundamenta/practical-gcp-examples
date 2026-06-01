import datetime
import decimal

from google.cloud import bigquery

MAX_ROWS = 5000  # aggregates are small by construction; this is a safety cap


def _json_safe(v):
    # BigQuery DATE/DATETIME/TIME/TIMESTAMP columns return Python date/datetime/time objects;
    # NUMERIC/BIGNUMERIC return Decimal — none are JSON serializable.
    if isinstance(v, (datetime.date, datetime.time)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return v


def run_query_rows(sql: str, client: bigquery.Client, *, max_bytes: int = 1 << 30) -> list[dict]:
    cfg = bigquery.QueryJobConfig(use_query_cache=True, maximum_bytes_billed=max_bytes)
    job = client.query(sql, job_config=cfg)
    rows = [{k: _json_safe(v) for k, v in dict(r).items()} for r in job.result(max_results=MAX_ROWS)]
    return rows
