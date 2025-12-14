#!/bin/bash
# Run BigQuery Data Insight Builder with verbose debugging

echo "Starting BigQuery Data Insight Builder in DEBUG mode..."
echo "========================================="
echo ""

# Set Python to be more verbose
export PYTHONUNBUFFERED=1

# Run with uvicorn in reload mode with access logs
uv run python -m uvicorn app.main:app \
    --reload \
    --port 8080 \
    --log-level debug \
    --access-log
