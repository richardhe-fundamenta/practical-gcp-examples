#!/bin/bash
# Run BigQuery MCP Studio with verbose debugging

echo "Starting BigQuery MCP Studio in DEBUG mode..."
echo "========================================="
echo ""

# Set Python to be more verbose
export PYTHONUNBUFFERED=1

# Run with uvicorn in reload mode with access logs
uv run uvicorn app.main:app \
    --reload \
    --port 8080 \
    --log-level debug \
    --access-log
