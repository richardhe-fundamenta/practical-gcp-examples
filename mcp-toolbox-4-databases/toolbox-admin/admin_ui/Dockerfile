# Production Dockerfile for Admin UI - FastAPI web application
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
ENV PATH="/root/.cargo/bin:$PATH"

# Copy dependency files from project root
# NOTE: Build context must be the project root directory
# Build command: docker build -f admin_ui/Dockerfile .
COPY pyproject.toml ./pyproject.toml

# Copy admin_ui application code (needed before install for editable mode)
COPY admin_ui ./admin_ui/

# Install Python dependencies using uv (editable mode requires source files)
RUN uv pip install --system -e .

# Set working directory to admin_ui
WORKDIR /app/admin_ui

# Environment variables (can be overridden at runtime)
ENV PROJECT_ID="" \
    REGISTRY_DATASET="example_mcp_toolbox_4_dbs" \
    REGISTRY_TABLE="query_registry" \
    BIGQUERY_SOURCE_NAME="bigquery-source" \
    TOOLS_FILE="/app/tools.yaml" \
    DEBUG_MODE="false" \
    SECRET_NAME="mcp-tools-yaml" \
    LOG_LEVEL="INFO" \
    PYTHONUNBUFFERED=1

# Cloud Run sets PORT environment variable, default to 8080
ENV PORT=8080

# Uvicorn configuration for production
# Workers: 1 per CPU core (Cloud Run auto-scales containers)
# For Cloud Run, use 1 worker and let Cloud Run handle scaling
ENV UVICORN_WORKERS=1 \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_LOG_LEVEL=info

# Expose port (Cloud Run will set this dynamically)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run with Uvicorn for production
# --host 0.0.0.0 - Listen on all interfaces
# --port $PORT - Use Cloud Run's PORT environment variable
# --workers 1 - Single worker (Cloud Run handles scaling)
# --log-level - Set log level from env
# --proxy-headers - Trust proxy headers (required for Cloud Run)
# --forwarded-allow-ips '*' - Trust all proxy IPs (Cloud Run requirement)
CMD exec uvicorn app:app \
    --host ${UVICORN_HOST} \
    --port ${PORT} \
    --workers ${UVICORN_WORKERS} \
    --log-level ${UVICORN_LOG_LEVEL} \
    --proxy-headers \
    --forwarded-allow-ips '*'
