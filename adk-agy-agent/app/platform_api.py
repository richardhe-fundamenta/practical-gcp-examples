"""Endpoint helpers for the Managed Agents + Interactions APIs.

Verified against the live v1beta1 API + google-genai SDK — see
docs/NOTES-platform-api.md. Both APIs live at the GLOBAL host; ``location`` is
``global``.
"""

HOST = "https://aiplatform.googleapis.com/v1beta1"


def agent_url(project, location, agent_id):
    """Single agent resource URL (used for the preflight existence check)."""
    return f"{HOST}/projects/{project}/locations/{location}/agents/{agent_id}"


def interactions_url(project, location):
    """Interactions create endpoint (POST). Bare collection, not ``:create``."""
    return f"{HOST}/projects/{project}/locations/{location}/interactions"


def interaction_url(project, location, interaction_id):
    """Single interaction URL (GET, for polling a background interaction)."""
    return f"{HOST}/projects/{project}/locations/{location}/interactions/{interaction_id}"
