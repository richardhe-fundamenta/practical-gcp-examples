import requests
import json
import os

from typing import Callable
from a2a_utils import get_gcloud_access_token
from urllib.parse import urlencode, urlunparse

def construct_google_oauth_uri(client_id: str, scopes: list[str]) -> str:
    """
    Constructs the fully parameterized Google OAuth Authorization URI.

    This URI is used to initiate the server-side OAuth 2.0 flow.

    Args:
        client_id: The OAuth 2.0 client ID.
        scopes: A list of Google API scopes to request.

    Returns:
        The complete, URL-encoded authorization URI string.
    """
    
    # Base URL components (same as your example: https://accounts.google.com/o/oauth2/v2/auth)
    scheme = 'https'
    netloc = 'accounts.google.com'
    path = '/o/oauth2/v2/auth'
    
    # Required parameters for a server-side OAuth flow for Discovery Engine/Vertex AI Search
    params = {
        'client_id': client_id,
        # This is the required redirect URI for Google Cloud to handle the token exchange
        'redirect_uri': 'https://vertexaisearch.cloud.google.com/static/oauth/oauth.html',
        # Join scopes into a space-separated string
        'scope': ' '.join(scopes), 
        'include_granted_scopes': 'true',
        'response_type': 'code',
        'access_type': 'offline', # Required to get a refresh token
        'prompt': 'consent' # Forces the user to re-consent, which is often good practice for offline access
    }
    
    # Encode the parameters into a query string
    query = urlencode(params)
    
    # Assemble the final URI
    return urlunparse((scheme, netloc, path, '', query, ''))

def create_auth_resource(
    project_id: str,
    location: str,
    auth_id: str,
    oauth_client_id: str,
    oauth_client_secret: str,
    oauth_auth_uri: str,
    oauth_token_uri: str,
) -> dict:
    """
    Creates a server-side OAuth 2.0 Authorization resource in Google Cloud Discovery Engine.

    Args:
        project_id: The Google Cloud project ID.
        location: The location/region of the Discovery Engine instance (e.g., 'global').
        auth_id: The user-defined authorization ID for the new resource.
        oauth_client_id: The OAuth 2.0 client ID.
        oauth_client_secret: The OAuth 2.0 client secret.
        oauth_auth_uri: The OAuth 2.0 authorization URI.
        oauth_token_uri: The OAuth 2.0 token URI.

    Returns:
        The JSON response from the API call as a dictionary.
        
    Raises:
        requests.exceptions.HTTPError: If the API call returns a non-200 status code.
    """
    
    # 1. Get the Access Token
    access_token = get_gcloud_access_token()

    # 2. Construct the API Endpoint URL
    base_url = f"https://discoveryengine.googleapis.com"
    api_path = (
        f"/v1alpha/projects/{project_id}/locations/{location}/authorizations"
        f"?authorizationId={auth_id}"
    )
    url = base_url + api_path
    
    # 3. Define Headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }
    
    # 4. Define Request Body (Payload)
    payload = {
        "name": f"projects/{project_id}/locations/{location}/authorizations/{auth_id}",
        "serverSideOauth2": {
            "clientId": oauth_client_id,
            "clientSecret": oauth_client_secret,
            "authorizationUri": oauth_auth_uri,
            "tokenUri": oauth_token_uri
        }
    }

    # 5. Make the POST Request
    response = requests.post(url, headers=headers, data=json.dumps(payload))

    # 6. Check for Errors (equivalent to a non-zero exit code in curl)
    response.raise_for_status() 

    # 7. Return the successful response
    return response.json()

if __name__ == '__main__':
    CLIENT_ID = os.environ.get("CLIENT_ID")
    CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
    AUTH_ID = "auth-id-gemini-enterprise-17632265_176322653154"

    PROJECT_ID = "rocketech-de-pgcp-sandbox"
    PROJECT_NUMBER = "630458277802"
    LOCATION = "global"
   
    CLOUD_RUN_SERVICE_NAME = "a2a-weather-agent"

    # Scopes needed for BigQuery access (used as an example from your description)
    REQUIRED_SCOPES = [
        "https://www.googleapis.com/auth/cloud-platform",
    ]
    
    # --- CONSTRUCT THE AUTH URI ---
    AUTH_URI = construct_google_oauth_uri(
        client_id=CLIENT_ID,
        scopes=REQUIRED_SCOPES
    )

    try:
        result = create_auth_resource(
            project_id=PROJECT_ID,
            location=LOCATION,
            auth_id=AUTH_ID,
            oauth_client_id=CLIENT_ID,
            oauth_client_secret=CLIENT_SECRET,
            oauth_auth_uri=AUTH_URI,
            oauth_token_uri="https://oauth2.googleapis.com/token"
        )
        print("\n✅ Authorization Request Sent Successfully (May be an Operation response if asynchronous):")
        print(json.dumps(result, indent=2))
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ API Error ({e.response.status_code}):")
        print(e.response.text)
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
