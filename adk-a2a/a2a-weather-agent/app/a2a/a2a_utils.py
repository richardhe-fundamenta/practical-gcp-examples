import requests
import json
import subprocess

from typing import Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH


def fetch_token(service_url) -> str:
    try:
        token = id_token.fetch_id_token(Request(), service_url)
        return token
    except Exception as e:
        raise RuntimeError(f"Failed to fetch ID token: {e}")

def get_gcloud_access_token() -> str:
    """
    Retrieves the access token from the gcloud CLI environment.

    Raises:
        RuntimeError: If gcloud fails to execute or return a token.
    """
    try:
        # Execute the gcloud command to get the access token
        access_token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"], 
            text=True
        ).strip()
        
        if not access_token:
            raise RuntimeError("gcloud returned an empty token.")

        return access_token
        
    except Exception as e:
        # Catch all possible errors (FileNotFoundError, CalledProcessError, etc.)
        raise RuntimeError(
            f"Failed to retrieve gcloud access token. Ensure gcloud is installed and authenticated. Error: {e}"
        )

def fetch_a2a_agent_card(agent_url: str, agent_rpc_path: str) -> Optional[Dict[str, Any]]:
    """
    Fetches the A2A Agent Card from the correctly configured REST endpoint 
    for an agent deployed using the A2A server library.

    Args:
        agent_url: The base URL of the A2A agent's REST endpoint (e.g., the Cloud Run service URL).
        agent_rpc_path: The base RPC path defined in the server code (e.g., /a2a/app).

    Returns:
        A dictionary containing the parsed Agent Card JSON, or None if the
        request fails or the content is invalid.
    """
    
    # We use the base URL provided (e.g., https://your-service.run.app)
    base_url = agent_url.strip().rstrip('/')
    
    # The Agent Card lives at the RPC path PLUS the well-known path.
    # e.g., https://service.run.app/a2a/app/.well-known/agent-card
    url = f"{base_url}{agent_rpc_path}{AGENT_CARD_WELL_KNOWN_PATH}"
    
    token = fetch_token(agent_url)
    
    # Standard headers for a JSON request
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    print(f"Attempting to fetch Agent Card from: {url}")

    try:
        # Use a timeout to prevent hanging indefinitely
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check for successful HTTP status code (200 OK)
        response.raise_for_status()
        
        # Parse the JSON content
        agent_card = response.json()
        
        # Basic validation (optional but recommended for a protocol)
        if not isinstance(agent_card, dict) or "protocolVersion" not in agent_card:
            print("Error: Fetched data is not a valid A2A Agent Card (missing 'protocolVersion').")
            return None
            
        print("✅ Successfully fetched and parsed Agent Card.")
        return agent_card
        
    except requests.exceptions.Timeout:
        print(f"Error: Request timed out after 10 seconds while fetching {url}")
    except requests.exceptions.RequestException as e:
        print(f"Error: HTTP request failed for {url}. Details: {e}")
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON response from {url}. Response text: {response.text[:100]}...")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    return None


