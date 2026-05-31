from unittest.mock import MagicMock
import pytest
from app.bigquery.validation import validate_sql, ValidationError

class _Ref:
    def __init__(self, dataset_id): self.dataset_id = dataset_id

def _client(bytes_processed, datasets, raises=None):
    c = MagicMock()
    if raises:
        c.query.side_effect = raises
    else:
        job = MagicMock()
        job.total_bytes_processed = bytes_processed
        job.referenced_tables = [_Ref(d) for d in datasets]
        c.query.return_value = job
    return c

def test_valid_query_passes():
    c = _client(1000, ["analytics"])
    info = validate_sql("SELECT 1", c, max_bytes=10_000, allowlist={"analytics"})
    assert info.total_bytes == 1000

def test_over_cap_rejected():
    c = _client(20_000, ["analytics"])
    with pytest.raises(ValidationError, match="byte cap"):
        validate_sql("SELECT 1", c, max_bytes=10_000, allowlist={"analytics"})

def test_disallowed_dataset_rejected():
    c = _client(100, ["secret_pii"])
    with pytest.raises(ValidationError, match="not allowlisted"):
        validate_sql("SELECT 1", c, max_bytes=10_000, allowlist={"analytics"})

def test_invalid_sql_rejected():
    from google.api_core.exceptions import BadRequest
    c = _client(0, [], raises=BadRequest("Syntax error"))
    with pytest.raises(ValidationError, match="invalid SQL"):
        validate_sql("SELEC 1", c, max_bytes=10_000, allowlist={"analytics"})
