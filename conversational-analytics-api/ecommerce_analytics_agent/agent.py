import logging
import os
import pandas as pd

from google.adk.agents import Agent
from google.cloud import geminidataanalytics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adk_ecommerce_analytics_agent")
logger.setLevel(logging.INFO)


def parse_data_response(results, resp) -> dict:
    if 'query' in resp:
        query = resp.query
        results['query'] = {
            'name': query.name,
            'question': query.question,
        }
    elif 'generated_sql' in resp:
        results['generated_sql'] = resp.generated_sql
    elif 'result' in resp:
        fields = [field.name for field in resp.result.schema.fields]
        d = {}
        for el in resp.result.data:
            for field in fields:
                if field in d:
                    d[field].append(el[field])
                else:
                    d[field] = [el[field]]

        results['data'] = pd.DataFrame(d).to_json(orient='records')

    return results


def ecommerce_analytics(question: str) -> dict:
    """Help the user analyse their e-commerce data."""

    project_id = os.environ.get("PROJECT_ID", "rocketech-de-pgcp-sandbox")
    data_agent_id = os.environ.get("DATA_AGENT_ID", "ecommerce_analytics_data_agent")
    data_agent_context = geminidataanalytics.DataAgentContext()
    data_agent_context.data_agent = f"projects/{project_id}/locations/global/dataAgents/{data_agent_id}"

    # Make calls to the API - Single turn stateless conversation
    data_chat_client = geminidataanalytics.DataChatServiceClient()

    # Create a request that contains a single user message (your question)
    messages = [geminidataanalytics.Message()]
    messages[0].user_message.text = question

    # Form the request
    request = geminidataanalytics.ChatRequest(
        parent=f"projects/{project_id}/locations/global",
        messages=messages,
        data_agent_context=data_agent_context
    )

    # Make the request
    stream = data_chat_client.chat(request=request)

    # Handle the response
    results = {}
    for response in stream:
        logger.debug(response)  # This will help you understand the output structure when developing
        m = response.system_message
        if 'data' in m:
            results = parse_data_response(results, getattr(m, 'data'))

    if results is not {}:
        return {"status": "success", "results": results}
    else:
        return {"status": "error", "message": "No data received"}


root_agent = Agent(
    name="adk_ecommerce_analytics_agent",
    model="gemini-2.5-flash",
    description=(
        "Ecommerce agent answering questions"
    ),
    instruction=(
        "You are a helpful agent who can answer user questions about analytics."
        "First, you should call the ecommerce_analytics tool to get the data."
        "Then, you should format the output into two sections, "
        "1. Display the SQL ran, extract this from results['generated_sql']"
        "2. Display the data in a matrix, extract this from results['data']"
    ),
    tools=[
        ecommerce_analytics
    ],
)
