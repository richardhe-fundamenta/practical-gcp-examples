# BigQuery MCP Examples

Two complementary applications demonstrating BigQuery analytics workflows using MCP (Model Context Protocol).

## Architecture

![Architecture Diagram](./architecture-diagram.png)
*Upload your architecture diagram to visualize how these components work together*

## Components

### [bigquery-data-insight-builder](./bigquery-data-insight-builder)
GUI application for creating, testing, and maintaining a curated library of parameterized SQL queries. Data analysts use this to build and validate production-ready queries with MCP assistance.

### [bigquery-analytics-agent](./bigquery-analytics-agent)
Dual-mode analytics agent built with Google's ADK. Supports both ad-hoc query generation (Explore mode) and access to curated reports from the insight builder (Production mode).

## Setup

### 1. Enable MCP on the Project

```bash
gcloud beta services mcp enable bigquery.googleapis.com \
    --project=rocketech-de-pgcp-sandbox
```

### 2. Grant Permissions

Grant the following roles to the appropriate users or service accounts:

- **Service Usage Admin** (`roles/serviceusage.serviceUsageAdmin`) - Enable APIs and MCP servers in the project
- **MCP Tool User** (`roles/mcp.toolUser`) - Make MCP tool calls
- **BigQuery Job User** (`roles/bigquery.jobUser`) - Run BigQuery jobs
- **BigQuery Data Viewer** (`roles/bigquery.dataViewer`) - Query BigQuery data

### 3. User Project Header

The Google user project header is required, especially when running locally:

```bash
--header "x-goog-user-project: <replace with your project id>"
```

## How They Work Together

1. **Build**: Use the insight builder to create and test parameterized queries
2. **Deploy**: Save approved queries to Cloud Datastore
3. **Consume**: Analytics agent accesses the curated query library in Production mode

## Userful to Read
- [BigQuery MCP Main Doc](https://docs.cloud.google.com/bigquery/docs/use-bigquery-mcp)
- [BigQuery MCP Tools Overview](https://docs.cloud.google.com/bigquery/docs/reference/mcp/tools_overview)
