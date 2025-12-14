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

## How They Work Together

1. **Build**: Use the insight builder to create and test parameterized queries
2. **Deploy**: Save approved queries to Cloud Datastore
3. **Consume**: Analytics agent accesses the curated query library in Production mode
