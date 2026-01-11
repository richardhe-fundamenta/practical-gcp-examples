# BigQuery Remote Function Agent (ADK)

![Architecture Diagram](./bq-batch-remote-fun-adk.png)

A scalable multi-agent system (Customer Advisor) built with Google's Agent Development Kit (ADK) designed to run as a BigQuery Remote Function (Cloud Run). It orchestrates specialized agents (Security, Billing, Retention) to analyze customer data in parallel.

## Project Structure

This project is organized as follows:

```
bq-remote-function-agent/
├── bq_import_data.py       # Script to load test data to BQ
└── customer-advisor              # ADK Customer Advisor Agent
    ├── app/
    │   ├── agent.py            # Multi-agent logic (ParallelAgent + Specialists)
    │   ├── fast_api_app.py     # BigQuery Remote Function Handler (FastAPI)
    │   └── app_utils/          # Telemetry and utilities
    ├── data/
    │   └── customer_scenarios.json # Test data for BigQuery simulation
    ├── tests/
    │   └── integration/
    │       └── test_bq_process.py  # End-to-end integration test
    ├── Makefile                # Build and deployment commands
    ├── Dockerfile              # Container definition for Cloud Run
    └── pyproject.toml          # Project dependencies (uv)
```

> 💡 **Tip:** Use [Gemini CLI](https://github.com/google-gemini/gemini-cli) for AI-assisted development - project context is pre-configured in `GEMINI.md`.

## BigQuery Remote Function Testing

We have included a comprehensive integration test that verifies the full end-to-end flow using 10 complex customer scenarios. This test validates the agent logic, session management, and response format.

**Run the automated test:**
```bash
cd customer-advisor
uv run pytest tests/integration/test_bq_process.py
```

This test:
1.  Mimics the BigQuery Remote Function call independently.
2.  Sends the payload from `data/customer_scenarios.json`.
3.  Validates the agent's response for correctness (Security, Billing, Retention handling).

### Manual Local Testing (Uvicorn)

If you want to run the server and test it manually:

1. **Start the local server:**
```bash
cd customer-advisor
uv run uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8011
```

2. **Send test payload:**
In another terminal (from the `customer-advisor` directory), run:
```bash
curl -X POST http://localhost:8011/ \
  -H "Content-Type: application/json" \
  -d @data/customer_scenarios.json | jq .
```

## Deploy to Cloud Run

You can deploy your agent to a Dev Environment using the following command:

```bash
cd customer-advisor
gcloud config set project <your-dev-project-id>
make deploy
```

## BigQuery Setup & Remote Function

### 1. Import Test Data
Run the provided script to load the customer scenarios into BigQuery:
```bash
# Run from the bq-remote-function-agent folder
python3 bq_import_data.py
```
This script populates the `customer_scenarios` table in the `rocketech-de-pgcp-sandbox.bigquery_remotefunction_examples` dataset.

### 2. Create the Remote Function
After deploying the Cloud Run service, define the Remote Function in BigQuery:

1. **Create a Connection**: Set up a BigQuery Cloud Resource Connection in `us-central1`.
2. **Grant Permissions**: Assign the `Cloud Run Service Invoker` role to the connection's service account for your Cloud Run service.
3. **Define Function**:
```sql
CREATE OR REPLACE FUNCTION `rocketech-de-pgcp-sandbox.bigquery_remotefunction_examples.analyze_customer`(customer_data JSON) 
RETURNS STRING
REMOTE WITH CONNECTION `rocketech-de-pgcp-sandbox.us-central1.your-connection-id`
OPTIONS (
  endpoint = 'https://YOUR_CLOUD_RUN_URL/',
  max_batching_rows = 10
);
```

### 3. Run Analysis in SQL
Call the agent across your entire dataset directly via SQL:
```sql
SELECT 
  customer_id, 
  `rocketech-de-pgcp-sandbox.bigquery_remotefunction_examples.analyze_customer`(TO_JSON(t)) as agent_analysis
FROM 
  `rocketech-de-pgcp-sandbox.bigquery_remotefunction_examples.customer_scenarios` AS t;
```



