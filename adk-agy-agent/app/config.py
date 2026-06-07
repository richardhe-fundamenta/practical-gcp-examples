import os

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "rocketech-de-pgcp-sandbox")
# Agents/Interactions API live at the GLOBAL endpoint (regional is unsupported).
# This is distinct from the GCS bucket region (us-central1).
LOCATION = os.environ.get("MANAGED_AGENT_LOCATION", "global")
MANAGED_AGENT_ID = os.environ.get("MANAGED_AGENT_ID", "agy-skill-agent")
# Managed-agent interactions run with background=true, so we poll for completion.
INTERACT_TIMEOUT_S = int(os.environ.get("INTERACT_TIMEOUT_S", "300"))
POLL_INTERVAL_S = float(os.environ.get("INTERACT_POLL_INTERVAL_S", "3"))
# Include the managed agent's reasoning + tool-call trace in the tool result so
# you can see what it did (set to 0 to return only the final answer).
SHOW_STEPS = os.environ.get("MANAGED_AGENT_SHOW_STEPS", "1").lower() in ("1", "true", "yes")
