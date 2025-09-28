# The Ecom Analytics Agent Frontend

## How to run locally
```
uv sync
export ENGINE_ID=<Agent Engine ID>;
export GOOGLE_CLOUD_PROJECT=<Project ID>
export GOOGLE_GENAI_USE_VERTEXAI=True
export PROJECT_ID=<Project ID>
export GOOGLE_CLOUD_LOCATION=europe-west4
uv run uvicorn src.main:app --reload
```

## Resources
- IAP Auth examples: https://github.com/googlecodelabs/user-authentication-with-iap
