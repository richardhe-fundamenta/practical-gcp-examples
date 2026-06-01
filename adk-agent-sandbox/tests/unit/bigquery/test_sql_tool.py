from unittest.mock import patch, MagicMock
from app.bigquery import sql_tool


def _fake_settings():
    s = MagicMock()
    s.max_bytes_billed = 10_000
    s.dataset_allowlist = frozenset({"analytics"})
    return s


def test_validation_failure_blocks_execution():
    with patch.object(sql_tool, "get_settings", return_value=_fake_settings()), \
         patch.object(sql_tool, "validate_sql", side_effect=sql_tool.ValidationError("byte cap")), \
         patch.object(sql_tool, "run_query_rows") as run:
        out = sql_tool.validate_and_run_sql("SELECT 1", _client=MagicMock())
        assert out["status"] == "rejected"
        assert "byte cap" in out["error"]
        run.assert_not_called()


def test_success_returns_rows():
    with patch.object(sql_tool, "get_settings", return_value=_fake_settings()), \
         patch.object(sql_tool, "validate_sql"), \
         patch.object(sql_tool, "run_query_rows", return_value=[{"a": 1}]):
        out = sql_tool.validate_and_run_sql("SELECT 1", _client=MagicMock())
        assert out["status"] == "ok"
        assert out["rows"] == [{"a": 1}]


def test_run_validated_sql_delegates_and_stores_rows():
    """run_validated_sql delegates to validate_and_run_sql AND stores the rows in state
    so the renderer can chart only real, queried data."""
    expected = {"status": "ok", "rows": [{"x": 42}]}
    ctx = MagicMock()
    ctx.state = {}
    with patch.object(sql_tool, "validate_and_run_sql", return_value=expected) as mock_inner:
        out = sql_tool.run_validated_sql("SELECT 42 AS x", ctx)
        mock_inner.assert_called_once_with("SELECT 42 AS x")
        assert out == expected
        assert ctx.state[sql_tool.VALIDATED_ROWS_KEY] == [{"x": 42}]


def test_run_validated_sql_rejected_does_not_store():
    rejected = {"status": "rejected", "error": "bad"}
    ctx = MagicMock()
    ctx.state = {}
    with patch.object(sql_tool, "validate_and_run_sql", return_value=rejected):
        out = sql_tool.run_validated_sql("SELECT 1", ctx)
        assert out == rejected
        assert sql_tool.VALIDATED_ROWS_KEY not in ctx.state
