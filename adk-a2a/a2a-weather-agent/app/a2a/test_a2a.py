import asyncio
import json
import os
import requests
import uuid
from google.auth.transport.requests import Request
from google.oauth2 import id_token

import vertexai
from a2a.types import (
    Message,
    MessageSendParams,
    Part,
    Role,
    SendStreamingMessageRequest,
    TextPart,
)

from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService


# --- Configuration ---
PROJECT_ID = "rocketech-de-pgcp-sandbox"
PROJECT_NUMBER = "630458277802"
LOCATION = "us-central1"
CLOUD_RUN_SERVICE_NAME = "a2a-weather-agent"

# Construct the Cloud Run URL dynamically
SERVICE_URL = f"https://{CLOUD_RUN_SERVICE_NAME}-{PROJECT_NUMBER}.{LOCATION}.run.app"

try:
    # To call a secured Cloud Run service, you need an ID token.
    # The 'audience' of the ID token must be the URL of the service you are calling.
    # google.auth.default() will find the credentials automatically in a GCP environment.
    print(f"Fetching ID token for audience: {SERVICE_URL}")
    id_token_info = id_token.fetch_id_token(Request(), SERVICE_URL)
    print(f"Successfully obtained ID token: {id_token_info[:10]}...")
except Exception as e:
    print("❌ Could not obtain an ID token.")
    print("Ensure the environment has credentials and the necessary permissions (e.g., 'Cloud Run Invoker' role).")
    print(f"Error details: {e}")
    exit(1)

client = vertexai.Client(
    project=PROJECT_ID,
    location=LOCATION,
)

message = Message(
    message_id=f"msg-user-{uuid.uuid4()}",
    role=Role.user,
    parts=[Part(root=TextPart(text="Hello! Weather in New York?"))],
)

request = SendStreamingMessageRequest(
    id=f"req-{uuid.uuid4()}",
    params=MessageSendParams(message=message),
)

# Set up headers with authentication
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {id_token_info}"}

try:
    # Send the streaming request to the A2A endpoint
    response = requests.post(
        f"{SERVICE_URL}/a2a/app",
        headers=headers,
        json=request.model_dump(mode="json", exclude_none=True),
        stream=True,
        timeout=60,
    )

    response.raise_for_status()  # Raise an exception for bad status codes

    print(f"Response status code: {response.status_code}")

    # Parse streaming A2A responses
    for line in response.iter_lines():
        if line:
            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                event_json = line_str[6:]
                event = json.loads(event_json)
                print(f"Received event: {event}")
except requests.exceptions.HTTPError as e:
    print(f"HTTP Error: {e}")
    if e.response is not None:
        print(f"Response status code: {e.response.status_code}")
        print(f"Response content: {e.response.text}")
    raise # Re-raise the exception after printing the content
