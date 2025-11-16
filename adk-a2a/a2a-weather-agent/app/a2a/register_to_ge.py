import requests
import json
import subprocess

from typing import Optional, List, Dict, Any
from a2a_utils import fetch_a2a_agent_card, get_gcloud_access_token
from typing import Optional

def register_a2a_agent(
    project_number: str,
    app_id: str,
    agent_name: str,
    agent_display_name: str,
    agent_description: str,
    agent_card_json_string: str,
    endpoint_location: str = "global-",
    location: str = "global",
    auth_id: Optional[str] = None
) -> requests.Response:
    """
    Registers an A2A agent with Gemini Enterprise via the Discovery Engine API.

    This function relies on a gcloud-authenticated environment to retrieve an access token.
    It expects the 'agent_card_json_string' to be a fully formed JSON string
    (e.g., produced by json.dumps()) containing the protocolVersion, url, version,
    skills, capabilities, and other required A2A Agent Definition fields.

    Args:
        project_number: The number of your Google Cloud project.
        app_id: The ID of the Gemini Enterprise app.
        agent_name: The unique identifier for the agent (must match the 'name' in the JSON string).
        agent_display_name: The display name shown in the web app.
        agent_description: A description of the agent's function.
        agent_card_json_string: The complete, pre-serialized JSON string (the Agent Card)
                                  defining the A2A agent's technical configuration.
        endpoint_location: Multi-region prefix for the API request (e.g., 'global-').
        location: Multi-region of your data store (e.g., 'global').
        auth_id: Optional authorization ID for Google Cloud resource access.

    Returns:
        The requests.Response object from the API call.
    """

    # Build Request Body (Outer JSON payload)
    # The agent_card_json_string is passed directly into the 'jsonAgentCard' field.
    request_body = {
        "name": agent_name,
        "displayName": agent_display_name,
        "description": agent_description,
        "a2aAgentDefinition": {
            "jsonAgentCard": agent_card_json_string
        }
    }
    
    # Include authorization config if an auth_id is provided
    if auth_id:
        request_body["authorizationConfig"] = {
            "agentAuthorization": f"projects/{project_number}/locations/{location}/authorizations/{auth_id}"
        }

    # Construct the URL
    api_url = (
        f"https://discoveryengine.googleapis.com/v1alpha/"
        f"projects/{project_number}/locations/{location}/collections/default_collection/"
        f"engines/{app_id}/assistants/default_assistant/agents"
    )

    # Fetch token
    access_token = get_gcloud_access_token()

    # Set Headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # 5. Make the POST Request
    print(f"Sending POST request to: {api_url}")
    response = requests.post(api_url, headers=headers, json=request_body)
    
    # Simple output for confirmation
    if response.status_code == 200:
        print("\n✅ Agent registration request successful.")
    else:
        # Print the error details if available
        print(f"\n❌ Agent registration request failed with status code {response.status_code}.")
        try:
            print("Response body:", response.json())
        except json.JSONDecodeError:
            print("Response body:", response.text)

    return response

# Fetch agent card from Cloud Run
# Important: running this code twice will register two identical agents in Gemini Enterprise, adapt the code as needed to make it do the update using docs here: https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent#update_an_a2a_agent
PROJECT_ID = "rocketech-de-pgcp-sandbox"
PROJECT_NUMBER = "630458277802"
LOCATION = "us-central1"
CLOUD_RUN_SERVICE_NAME = "a2a-weather-agent"
SERVICE_URL = f"https://{CLOUD_RUN_SERVICE_NAME}-{PROJECT_NUMBER}.{LOCATION}.run.app"

agent_card = fetch_a2a_agent_card(SERVICE_URL, '/a2a/app')

APP_ID = "gemini-enterprise-17632265_1763226531549"
AGENT_NAME = agent_card["name"] # Use the name from the card
AGENT_DISPLAY_NAME = "A2A Weather Agent"
AGENT_DESCRIPTION = "Simple A2A Weather Agent"
AGENT_CARD_JSON_STRING = json.dumps(agent_card)

# Optional: Set this if your agent requires specific authorization for Google Cloud resources
AUTH_ID = None # e.g., "my-agent-authorization-key" 

if __name__ == "__main__":
    print(f"Attempting to register agent: {AGENT_NAME}")
    
    try:
        response = register_a2a_agent(
            project_number=PROJECT_NUMBER,
            app_id=APP_ID,
            agent_name=AGENT_NAME,
            agent_display_name=AGENT_DISPLAY_NAME,
            agent_description=AGENT_DESCRIPTION,
            agent_card_json_string=AGENT_CARD_JSON_STRING,
            auth_id=AUTH_ID
        )

        # Print the final response details
        if response.status_code != 200:
            print(f"\nResponse details: {response.text}")
        
    except RuntimeError as e:
        print(f"\n🛑 Error during execution: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")