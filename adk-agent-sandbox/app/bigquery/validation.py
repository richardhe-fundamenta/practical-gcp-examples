from dataclasses import dataclass
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import bigquery

class ValidationError(Exception):
    """Raised when SQL fails the harness gate. Message is returned to the SQL writer."""

@dataclass(frozen=True)
class QueryInfo:
    total_bytes: int
    datasets: frozenset[str]

def validate_sql(sql: str, client: bigquery.Client, *, max_bytes: int,
                 allowlist: set[str]) -> QueryInfo:
    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    try:
        job = client.query(sql, job_config=cfg)
    except GoogleAPICallError as e:
        raise ValidationError(f"invalid SQL: {e.message if hasattr(e, 'message') else e}") from e
    datasets = frozenset(t.dataset_id for t in (job.referenced_tables or []))
    bad = datasets - set(allowlist)
    if bad:
        raise ValidationError(f"dataset(s) not allowlisted: {sorted(bad)}")
    if job.total_bytes_processed > max_bytes:
        raise ValidationError(
            f"query exceeds byte cap: {job.total_bytes_processed} > {max_bytes}; add filters/aggregation")
    return QueryInfo(total_bytes=job.total_bytes_processed, datasets=datasets)
