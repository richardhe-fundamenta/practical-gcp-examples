from google.cloud import bigquery
from app.config import get_settings
from app.bigquery.validation import validate_sql, ValidationError
from app.bigquery.execute import run_query_rows


def _bq_client(settings) -> bigquery.Client:
    return bigquery.Client(project=settings.project, location=settings.bq_data_region)


def validate_and_run_sql(sql: str, _client: bigquery.Client | None = None) -> dict:
    """Validate (dry-run: validity + byte cap + dataset allowlist) THEN execute.
    Returns {"status": "ok", "rows": [...]} or {"status": "rejected", "error": "..."}.
    This is the only BigQuery execution path; the gate cannot be skipped."""
    s = get_settings()
    client = _client or _bq_client(s)
    try:
        validate_sql(sql, client, max_bytes=s.max_bytes_billed, allowlist=set(s.dataset_allowlist))
    except ValidationError as e:
        return {"status": "rejected", "error": str(e)}
    rows = run_query_rows(sql, client, max_bytes=s.max_bytes_billed)
    return {"status": "ok", "rows": rows}


def run_validated_sql(sql: str) -> dict:
    """Validate a BigQuery SQL query through the harness dry-run gate (validity, byte cap,
    dataset allowlist) and, if it passes, execute it and return the rows.

    Args:
        sql: A read-only BigQuery Standard SQL SELECT query.
    Returns:
        {"status":"ok","rows":[...]} on success, or {"status":"rejected","error":"..."} if
        the query is invalid, exceeds the byte cap, or touches a non-allowlisted dataset.
    """
    return validate_and_run_sql(sql)
