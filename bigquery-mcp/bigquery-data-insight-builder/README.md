# BigQuery Data Insight Builder

A GUI application for creating, testing, and maintaining high-quality parameterized SQL queries that can be executed via the BigQuery MCP remote service.

## Purpose

BigQuery Data Insight Builder provides a curated library of production-ready SQL queries with:
- **Quality Control**: Test and validate queries before saving
- **Organization**: Group queries by category (finance, product, admin, etc.)
- **MCP Integration**: Use BigQuery MCP for query generation and execution
- **Parameterization**: Support for BigQuery native parameters (@param syntax)
- **Governance**: Maintain a registry of approved queries for business users

## Architecture

- **Frontend**: Alpine.js + Tailwind CSS (lightweight, no build step)
- **Backend**: FastAPI (serves both API and templates)
- **Database**: Cloud Datastore (query metadata and categories)
- **MCP**: [BigQuery MCP service](https://docs.cloud.google.com/bigquery/docs/use-bigquery-mcp) (query generation, validation, execution)
- **Deployment**: Cloud Run (single container)

## Workflow

1. **Create**: Data analysts use natural language to generate SQL via MCP
2. **Refine**: Review and edit the generated parameterized SQL
3. **Test**: Validate queries with test parameters before saving
4. **Save**: Store approved queries in Cloud Datastore

## Quick Start

```bash
# Set your GCP project ID
export PROJECT_ID="your-project-id"

# Install dependencies
uv sync

# Create required Cloud Datastore indexes
gcloud datastore indexes create index.yaml --project=$PROJECT_ID

# Wait for indexes to be created (check status)
gcloud datastore indexes list --project=$PROJECT_ID

# Run locally
uv run python -m uvicorn app.main:app --reload --port 8080

**Note**: The Datastore composite index creation typically takes 5-10 minutes. You can proceed with local development while it builds. The app uses client-side sorting until the index is ready.

## Project Structure

```md
bigquery-data-insight-builder/
├── app/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Datastore models
│   ├── mcp_service.py       # MCP integration
│   ├── routes/              # API routes
│   └── templates/           # HTML templates
├── static/                  # CSS, JS, images
├── index.yaml              # Datastore composite indexes
└── pyproject.toml          # Dependencies
```
