# Slide assets

`architecture.png` is the GCP architecture diagram shown on the "Clean GCP diagram" slide. It's
already generated and committed; if it's missing, that slide shows a fallback note.

## Regenerate with Nano Banana (Gemini image generation)

The committed image was produced with `gemini-3-pro-image-preview` (Nano Banana Pro) on Vertex AI
at location `global`, 16:9. To regenerate, use this prompt and save the result here as
`architecture.png`:

```
Create a clean, professional Google Cloud Platform architecture diagram. 16:9, light/white
background, flat modern style, generous whitespace, left-to-right flow, use OFFICIAL Google Cloud
product icons and the correct product logos, crisp readable labels.

Title at top: "A2A Agent with GKE Agent Sandbox".

Boxes and flow (left to right):
1. "Gemini Enterprise" (Gemini logo) — a chat panel with a user uploading a CSV file and a prompt.
2. Arrow labelled "A2A message/send (file + prompt)" to:
3. "Cloud Run" (Cloud Run icon) labelled "ADK A2UI Agent — run_code tool".
4. From Cloud Run, an arrow labelled "IAM-gated control plane + Direct VPC egress" UP to a large box
   "GKE Autopilot cluster — Agent Sandbox" (GKE icon) containing a small "sandbox-router (internal
   load balancer)" and an isolated "gVisor sandbox pod — no network, no credentials" running pandas
   + matplotlib producing chart.png.
5. From Cloud Run, an arrow DOWN to "Cloud Storage" (bucket icon) labelled "chart image + V4 signed
   URL (short TTL)".
6. A return arrow from Cloud Run back to Gemini Enterprise labelled "A2UI card: title, thinking, chart".

Small captions on arrows. No people other than a simple user icon. No fictional logos. Polished,
enterprise, presentation-ready.
```
