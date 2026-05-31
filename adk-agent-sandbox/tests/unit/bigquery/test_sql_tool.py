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
