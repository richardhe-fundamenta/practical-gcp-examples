# bigquery-analytics-agent

A dual-mode BigQuery analytics agent with curated report library built with Google's Agent Development Kit (ADK).

## Features

- **Explore Mode** (default): Generate and execute ad-hoc SQL queries automatically via BigQuery MCP
- **Production Mode**: Access curated reports organized by business topic from Cloud Datastore
- **Seamless Mode Switching**: Switch between modes anytime during conversation
- **Natural Language Report Explanations**: Understand what reports do without reading SQL

## Project Structure

This project is organized as follows:

```
bigquery-analytics-agent/
├── app/                 # Core application code
│   ├── agent.py         # Dual-mode agent logic
│   ├── agent_engine_app.py # Agent Engine application logic
│   ├── explore_tools.py # Explore mode tools (BigQuery MCP)
│   ├── production_tools.py # Production mode tools
│   ├── services/        # Service layer
│   │   └── datastore_service.py # Datastore integration
│   ├── shared/          # Shared models
│   │   └── models.py    # Datastore models
│   └── app_utils/       # App utilities and helpers
├── tests/               # Unit, integration, and load tests
├── Makefile             # Makefile for common commands
├── GEMINI.md            # AI-assisted development guide
└── pyproject.toml       # Project dependencies and configuration
```

> 💡 **Tip:** Use [Gemini CLI](https://github.com/google-gemini/gemini-cli) for AI-assisted development - project context is pre-configured in `GEMINI.md`.

## Requirements

Before you begin, ensure you have:
- **uv**: Python package manager (used for all dependency management in this project) - [Install](https://docs.astral.sh/uv/getting-started/installation/) ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with `uv add <package>`)
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)
- **make**: Build automation tool - [Install](https://www.gnu.org/software/make/) (pre-installed on most Unix-based systems)


## Quick Start (Local Testing)

Install required packages and launch the local development environment:

```bash
make install && make playground
```
> **📊 Observability Note:** Agent telemetry (Cloud Trace) is always enabled. Prompt-response logging (GCS, BigQuery, Cloud Logging) is **disabled** locally, **enabled by default** in deployed environments (metadata only - no prompts/responses). See [Monitoring and Observability](#monitoring-and-observability) for details.

## Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `make install`       | Install all required dependencies using uv                                                  |
| `make playground`    | Launch local development environment for testing agent |
| `make deploy`        | Deploy agent to Agent Engine |
| `make register-gemini-enterprise` | Register deployed agent to Gemini Enterprise ([docs](https://googlecloudplatform.github.io/agent-starter-pack/cli/register_gemini_enterprise.html)) |
| `make test`          | Run unit and integration tests                                                              |
| `make lint`          | Run code quality checks (codespell, ruff, mypy)                                             |

For full command options and usage, refer to the [Makefile](Makefile).


## Usage

This template follows a "bring your own agent" approach - you focus on your business logic, and the template handles everything else (UI, infrastructure, deployment, monitoring).
1. **Develop:** Edit your agent logic in `app/agent.py`.
2. **Test:** Explore your agent functionality using the local playground with `make playground`. The playground automatically reloads your agent on code changes.
3. **Enhance:** When ready for production, run `uvx agent-starter-pack enhance` to add CI/CD pipelines, Terraform infrastructure, and evaluation notebooks.

The project includes a `GEMINI.md` file that provides context for AI tools like Gemini CLI when asking questions about your template.

## Dual-Mode Operation

The agent supports two operating modes:

### Explore Mode (Default)
Generate and execute SQL queries automatically. Ask any questions about your BigQuery data.

**Example:**
```
User: "How many orders were placed in December 2024?"
Agent: [Generates SQL, executes, returns results]
```

### Production Mode
Access a library of curated reports organized by business topic. Each report is a pre-approved, parameterized query template managed via BigQuery MCP Studio.

**Workflow:**
1. Browse reports by topic: `"list categories"` or `"show available reports"`
2. Understand a report: `"tell me about [report name or ID]"` - get natural language explanation
3. Run a report with parameters: `"run customer details report with customer_id=12345"`

**Example:**
```
User: "What reports are available?"
Agent: [Shows categories like Finance, Sales, Customer Analytics with example reports]

User: "Tell me about the monthly revenue report"
Agent: [Explains what the report shows and what parameters it needs]

User: "Run it for December 2024"
Agent: [Executes report with provided parameters, returns results]
```

### Switching Modes

Use natural language to switch:
- **To Explore**: `"switch to explore mode"` or `"use ad-hoc queries"`
- **To Production**: `"activate production mode"` or `"show me the reports"`

The agent uses intent detection and allows switching anytime during conversation.


## Deployment

You can deploy your agent to a Dev Environment using the following command:

```bash
gcloud config set project <your-dev-project-id>
make deploy
```


When ready for production deployment with CI/CD pipelines and Terraform infrastructure, run `uvx agent-starter-pack enhance` to add these capabilities.

## Monitoring and Observability

The application provides two levels of observability:

**1. Agent Telemetry Events (Always Enabled)**
- OpenTelemetry traces and spans exported to **Cloud Trace**
- Tracks agent execution, latency, and system metrics

**2. Prompt-Response Logging (Configurable)**
- GenAI instrumentation captures LLM interactions (tokens, model, timing)
- Exported to **Google Cloud Storage** (JSONL), **BigQuery** (external tables), and **Cloud Logging** (dedicated bucket)

| Environment | Prompt-Response Logging |
|-------------|-------------------------|
| **Local Development** (`make playground`) | ❌ Disabled by default |

**To enable locally:** Set `LOGS_BUCKET_NAME` and `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=NO_CONTENT`.

See the [observability guide](https://googlecloudplatform.github.io/agent-starter-pack/guide/observability.html) for detailed instructions, example queries, and visualization options.
