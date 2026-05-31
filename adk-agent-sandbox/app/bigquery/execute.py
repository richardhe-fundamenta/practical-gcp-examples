from google.cloud import bigquery

MAX_ROWS = 5000  # aggregates are small by construction; this is a safety cap

def run_query_rows(sql: str, client: bigquery.Client, *, max_bytes: int = 1 << 30) -> list[dict]:
    cfg = bigquery.QueryJobConfig(use_query_cache=True, maximum_bytes_billed=max_bytes)
    job = client.query(sql, job_config=cfg)
    rows = [dict(r) for r in job.result(max_results=MAX_ROWS)]
    return rows
