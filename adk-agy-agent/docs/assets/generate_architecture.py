# /// script
# requires-python = ">=3.10"
# dependencies = ["google-genai"]
# ///
"""Regenerate docs/assets/architecture.png with Gemini 2.5 Flash Image ("nano banana").

Usage (needs `gcloud auth application-default login`):
    uv run docs/assets/generate_architecture.py
Env: GOOGLE_CLOUD_PROJECT (default rocketech-de-pgcp-sandbox).
"""
import os
import pathlib

from google import genai

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "rocketech-de-pgcp-sandbox")
OUT = pathlib.Path(__file__).with_name("architecture.png")

PROMPT = """Create a clean, professional software architecture diagram for a slide.
White background, flat modern design, Google Cloud color palette (blue, green, amber/yellow, purple),
rounded boxes with soft shadows, clear directional arrows, legible sans-serif labels. Left-to-right flow.

Elements and connections:
1. A simple person icon labeled "User" on the far left.
2. A box labeled "Gemini Enterprise". Arrow from "User" to it.
3. A green rounded box labeled "ADK Agent (Cloud Run)". Arrow labeled "A2A" from "Gemini Enterprise" to it.
4. An amber rounded box labeled "Managed Agent (sandbox)". Arrow labeled "Interactions API" from "ADK Agent" to it.
5. A blue database cylinder labeled "GCS Skills Bucket". A dashed arrow labeled "mounted on demand" from the bucket to the "Managed Agent".
6. A person icon labeled "Developer" near the bucket, with an arrow labeled "upload skill" pointing to the "GCS Skills Bucket".

Keep all labels short and clearly readable. Minimal, uncluttered, presentation quality, 16:9."""


def main() -> None:
    client = genai.Client(vertexai=True, project=PROJECT, location="global")
    resp = client.models.generate_content(model="gemini-2.5-flash-image", contents=PROMPT)
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            OUT.write_bytes(part.inline_data.data)
            print(f"saved {OUT} ({len(part.inline_data.data)} bytes)")
            return
    raise SystemExit("no image returned")


if __name__ == "__main__":
    main()
