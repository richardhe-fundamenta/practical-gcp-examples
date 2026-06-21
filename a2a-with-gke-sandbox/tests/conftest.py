import os

# app/agent.py calls google.auth.default() at import time; these defaults let
# the agent module import in tests/CI without real ADC. setdefault never
# overrides real credentials when they are present.
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "dummy")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "False")
