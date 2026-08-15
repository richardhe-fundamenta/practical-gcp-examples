# A collection of ADK agents

[![Subscribe on YouTube](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.socialcounts.org%2Fyoutube-live-subscriber-count%2FUC3XbEkSbPOzHvqNBrjNIu7A&query=%24.counters.api.subscriberCount&label=Subscribe&suffix=%20subscribers&color=FF0000&logo=youtube&logoColor=white&style=for-the-badge)](https://www.youtube.com/@practicalgcp2780?sub_confirmation=1)
[![Videos](https://img.shields.io/badge/90%2B_videos-Watch_all-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/playlist?list=UU3XbEkSbPOzHvqNBrjNIu7A)

_Code from the [PracticalGCP](https://www.youtube.com/@practicalgcp2780) YouTube channel._


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
python deploy_to_agentengine.py
```

### Test with Agent Engine

Use [adk_app_testing.ipynb](testing/adk_app_testing.ipynb) to query the deployed ADK agent on Agent Engine.