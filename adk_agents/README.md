# A collection of ADK agents

## ecom_analytics 

The ecom_analytics agent uses a GCP service called 
the conversational analytics API to convert natural language to SQL and shows the SQL executed and the results to the end user.

### Run locally
```
uv sync
source .venv/bin/activate
export GOOGLE_CLOUD_PROJECT=<replace with your project id>
export GOOGLE_GENAI_USE_VERTEXAI=True
export GOOGLE_CLOUD_LOCATION=europe-west4

adk web --reload_agents
```

### Deploy to Agent Engine
```
cd ecom_analytics
python deploy.py
```