from unittest.mock import MagicMock
from app.bigquery.execute import run_query_rows, MAX_ROWS

def test_run_returns_rows_capped():
    c = MagicMock()
    rows = [{"month": "2025-01", "region": "NA", "nrr": 101.0}]
    job = MagicMock()
    job.result.return_value = rows
    c.query.return_value = job
    out = run_query_rows("SELECT 1", c)
    assert out == rows
    _, kwargs = c.query.call_args
    assert kwargs["job_config"].maximum_bytes_billed is not None
