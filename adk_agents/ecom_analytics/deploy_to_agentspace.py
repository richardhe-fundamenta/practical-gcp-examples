import requests
import json
import subprocess

def deploy_agent_to_agentspace(
    project_id: str,
    project_number: str,
    reasoning_engine_id: str,
    reasoning_engine_location: str,
    as_app: str,
    as_location: str,
    agent_display_name: str = "teaching-assistant-agent",
    agent_description: str = """This agent acts as a friendly teaching assistant, checking the grammar of kids' questions, performing math calculations using corrected or original text (if grammatically correct), and providing results or grammar feedback in a friendly tone."""
):
    """
    Deploys an agent to AgentSpace using the Discovery Engine API.

    Args:
        project_id: Your Google Cloud Project ID.
        project_number: Your Google Cloud Project Number.
        reasoning_engine_id: Your Agent Engine ID (normally an 18-digit number).
        reasoning_engine_location: Location of your Agent Engine (e.g., us-central1).
        as_app: Your Agent Space Application ID.
        as_location: Location of your Agent Space Application (e.g., global, eu, us).
        agent_display_name: The name that will appear for the agent in AgentSpace.
        agent_description: A description of the agent's function.

    Returns:
        The JSON response from the API call.
    """

    # 1. Define derived variables
    reasoning_engine = f"projects/{project_id}/locations/{reasoning_engine_location}/reasoningEngines/{reasoning_engine_id}"
    discovery_engine_prod_api_endpoint = "https://discoveryengine.googleapis.com"
    api_url = (
        f"{discovery_engine_prod_api_endpoint}/v1alpha/projects/{project_number}/locations/{as_location}/collections/default_collection/engines/{as_app}/assistants/default_assistant/agents"
    )

    # 2. Get the access token using gcloud CLI
    try:
        # Note: This requires 'gcloud' CLI to be installed and authenticated
        access_token_result = subprocess.run(
            ['gcloud', 'auth', 'print-access-token'],
            capture_output=True,
            text=True,
            check=True
        )
        access_token = access_token_result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting access token: {e}")
        print("Please ensure 'gcloud' is installed and you are authenticated.")
        return None
    except FileNotFoundError:
        print("Error: 'gcloud' command not found.")
        print("Please ensure Google Cloud SDK is installed and configured in your PATH.")
        return None

    # 3. Define the request headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "x-goog-user-project": project_id,
    }

    # 4. Define the JSON payload (body)
    payload = {
        "name": f"projects/{project_number}/locations/{as_location}/collections/default_collection/engines/{as_app}/assistants/default_assistant",
        "displayName": agent_display_name,
        "description": agent_description,
        "icon": {
            "uri": "https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/corporate_fare/default/24px.svg"
        },
        "adk_agent_definition": {
            "tool_settings": {
                "toolDescription": agent_description,
            },
            "provisioned_reasoning_engine": {
                "reasoningEngine": reasoning_engine
            },
        }
    }

    # 5. Make the POST request
    print(f"Attempting to deploy agent to: {api_url}")
    try:
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        print("Agent deployment successful!")
        return response.json()
    except requests.exceptions.HTTPError as err:
        print(f"HTTP Error: {err}")
        print(f"Response Body: {response.text}")
        return None
    except requests.exceptions.RequestException as err:
        print(f"An error occurred during the API request: {err}")
        return None

# --- Example Usage ---
# Replace the placeholder values with your actual data

# Abstracted Variables (required parameters)
PROJECT_ID = "<gcp project id>"
PROJECT_NUMBER = "<gcp project number>" # i.e. run: gcloud projects describe <gcp project id> --format="value(projectNumber)"

REASONING_ENGINE_ID = "<replace with the deployed agent engine id>"
REASONING_ENGINE_LOCATION = "europe-west4"

AS_APP = "agentspace" # String
AS_LOCATION = "global" # String

# Optional Variables (using defaults defined in the function)
AGENT_DISPLAY_NAME = "<display name>"
AGENT_DESCRIPTION_TEXT = "<description text>"

# Call the function to deploy the agent
deployment_result = deploy_agent_to_agentspace(
    project_id=PROJECT_ID,
    project_number=PROJECT_NUMBER,
    reasoning_engine_id=REASONING_ENGINE_ID,
    reasoning_engine_location=REASONING_ENGINE_LOCATION,
    as_app=AS_APP,
    as_location=AS_LOCATION,
    # Uncomment and add values for optional parameters if needed
    agent_display_name=AGENT_DISPLAY_NAME,
    agent_description=AGENT_DESCRIPTION_TEXT
)

if deployment_result:
    print("\nDeployment Response:")
    print(json.dumps(deployment_result, indent=2))