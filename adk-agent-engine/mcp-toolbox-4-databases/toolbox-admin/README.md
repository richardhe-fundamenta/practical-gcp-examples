# BigQuery MCP Toolbox - Database-Driven Configuration

Scalable management of hundreds of BigQuery analytical queries through MCP Toolbox for Databases.

## Overview

This project provides a database-driven approach to managing large-scale BigQuery query tools for the MCP (Model Context Protocol) Toolbox. Instead of maintaining hundreds of queries in YAML files, queries are stored in a BigQuery registry table and dynamically generated into tools.yaml.

## Key Features

- **Web-Based Admin UI**: Manage queries through a FastAPI + HTMX interface
- **Modern UX**: Toast notifications and partial page updates (no full reloads)
- **Database-Driven**: Store and manage 100s of queries in BigQuery
- **Dynamic Generation**: Generate tools.yaml from database with one click
- **Toolset Organization**: Automatically organize queries by category/domain
- **Version Control**: Track query changes in the database
- **Team Collaboration**: Easy query management without YAML editing
- **Stateless Architecture**: No sessions required, optimized for Cloud Run

## Quick Start

### Prerequisites

- GCP Project with BigQuery enabled
- gcloud CLI installed and authenticated
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

### Install uv

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup

1. **Clone and configure**:
```bash
cd toolbox-admin
cp .env.example .env
# Edit .env with your project details
```

2. **Install dependencies**:
```bash
uv pip install -e .
```

3. **Create the query registry table**:
```bash
uv run scripts/deploy_schema.py
```

4. **Add sample queries**:
```bash
uv run scripts/populate_sample_queries.py
```

## Running the Application

The Admin UI is a FastAPI application that allows you to manage queries through a web interface:

### Start the FastAPI web server on port 8080
```bash
cd admin_ui
uv run python app.py
# Open http://0.0.0.0:8080
```

### Using the Admin UI

1. **View Queries**: The home page shows all queries with statistics
2. **Add Query**: Click "+ Add New Query" to create a new query
3. **Edit Query**: Click "Edit" on any query to modify it
4. **Enable/Disable**: Toggle queries on/off without deleting them
5. **Submit All Changes**: Click "Submit All Changes" to regenerate tools.yaml

### Start the MCP Toolbox Server

After generating tools.yaml, start the MCP Toolbox server:

```bash
# Make sure tools.yaml exists (generated via Admin UI)
# Start the toolbox server on port 8082
export OS="linux/amd64" # one of linux/amd64, darwin/arm64, darwin/amd64, or windows/amd64
curl -O https://storage.googleapis.com/genai-toolbox/v0.22.0/$OS/toolbox
chmod +x toolbox

./toolbox --tools-file tools.yaml --port 8082 --address 0.0.0.0
# Open http://0.0.0.0:8082

```

The toolbox server will now be running and ready to serve your BigQuery tools to MCP clients.

### Use the MCP UI Tool

The toolbox UI is a handy tool for testing

```bash
./toolbox --ui --tools-file tools.yaml --port 8083 --address 0.0.0.0

# Open http://0.0.0.0:8083/ui
```


## Project Structure

```
toolbox-admin/
├── README.md                # This file
├── admin_ui/
│   ├── app.py              # FastAPI web application
│   ├── Dockerfile          # Production Dockerfile (FastAPI + uvicorn)
│   ├── templates/          # HTML templates (Jinja2)
│   ├── static/             # Static files (CSS, JS)
│   └── utils/              # Utility modules
│       ├── bigquery_client.py
│       └── yaml_generator.py
├── config/
│   ├── schema.sql          # BigQuery registry table schema
│   └── sample_queries.sql  # Sample query data
├── scripts/
│   ├── deploy_schema.py    # Creates BigQuery registry table
│   └── populate_sample_queries.py
├── docs/
│   └── DEPLOYMENT.md       # Cloud Run deployment guide
├── .env.example            # Example environment variables
└── pyproject.toml          # Python project configuration
```
